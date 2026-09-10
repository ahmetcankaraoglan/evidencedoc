"""Model-led entity discovery with source-anchored occurrences, never guessed boxes."""
import hashlib
import time
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf as fitz

from .pipeline import anchor, norm
from .provider import NvidiaProvider, ProviderError
from .schemas import object_schema

CATEGORIES = ['person','organization','date','money','percentage','address','identifier',
              'contact','location','quantity','term','other']
ENTITY_SCHEMA = object_schema({
    'document_type': {'type':'string'}, 'summary': {'type':'string'},
    'suggested_fields': {'type':'array','items':{'type':'string'}},
    'entities': {'type':'array','items':object_schema({
        'value':{'type':'string'}, 'category':{'type':'string','enum':CATEGORIES},
        'role':{'type':'string'}, 'span_ids':{'type':'array','items':{'type':'string'}}})}
})


def precise_evidence(value, evidence, source_path):
    """Tighten PDF boxes only when a real search hit overlaps its cited span.

    Existing scanned/OCR documents retain honest line-level boxes. A model never
    supplies geometry. Each occurrence retains the full context line separately.
    """
    result = []
    doc = None
    try:
        if Path(source_path).read_bytes()[:5] == b'%PDF-':
            doc = fitz.open(source_path)
    except (OSError, fitz.FileDataError):
        pass
    try:
        for s in evidence:
            boxes = []
            if doc and s.get('source') == 'pdf-text':
                page = doc[s['page']-1]
                if page.rotation:
                    page.remove_rotation()
                for hit in page.search_for(value):
                    b = [hit.x0/page.rect.width,hit.y0/page.rect.height,
                         hit.x1/page.rect.width,hit.y1/page.rect.height]
                    a = s['bbox']
                    if b[0] < a[2]+.003 and b[2] > a[0]-.003 and b[1] < a[3]+.003 and b[3] > a[1]-.003:
                        boxes.append([round(max(0,min(1,x)),6) for x in b])
            # Context-only citations must not become occurrence boxes.
            if not boxes and any(norm(value) in norm(other['text']) for other in evidence) and norm(value) not in norm(s['text']):
                continue
            for b in boxes or [s['bbox']]:
                result.append({**s, 'bbox': b, 'context_bbox': s['bbox'],
                               'precision':'text-match' if boxes else 'source-line'})
    finally:
        if doc:
            doc.close()
    return result


def discover_entities(document, directory, provider=None, progress=None):
    started = time.monotonic()
    provider = provider or NvidiaProvider()
    pages = document['pages']
    indexed = {s['id']:s for s in document['spans']}
    task = ('Analyze this document page and discover its entities without a user-defined schema. '
            'Extract all distinct meaningful named entities, dates, monetary values, percentages, identifiers, '
            'addresses, contacts, locations, quantities and operative terms visible in these spans. '
            'For each value copy the shortest complete literal substring, cite source span IDs and assign '
            'a short natural-language role (no underscores) that distinguishes its context (e.g. current rate versus previous rate). '
            'Keep repeated values with different roles as separate entities. Do not extract standalone '
            'punctuation, table decoration, page numbers or generic filler words. '
            'Use contact only for an email, phone number or URL, never financial labels. '
            'Suggest 4–12 useful snake_case extraction fields appropriate to this document, prioritizing '
            'names, dates and operative amounts. Write document_type, summary and roles in English; '
            'preserve values in their original language. Never infer a missing value. '
            'Output at most 90 entities for this page, the most relevant first.')
    def one(page):
        spans = [s for s in document['spans'] if s['page'] == page['number']]
        if not spans:
            return {'document_type':'Unclassified','summary':'No readable text on this page.',
                    'suggested_fields':[],'entities':[]}
        return provider.ask(task, {'page':page['number'],
            'spans':[{'id':s['id'],'text':s['text']} for s in spans]}, schema=ENTITY_SCHEMA)
    outputs = []
    # At most three independent page calls; ordered results make merging stable.
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, response in enumerate(executor.map(one, pages), 1):
            outputs.append(response)
            if progress:
                progress(i, len(pages))
    entities, proposed, rejected, limits = {}, [], 0, []
    for page, response in zip(pages, outputs):
        rows = response.get('entities')
        if not isinstance(rows, list) or len(rows) > 150:
            raise ProviderError('NVIDIA returned an invalid entity list.')
        if len(rows) >= 90:
            limits.append(page['number'])
        for name in response.get('suggested_fields', []):
            if isinstance(name,str) and re.fullmatch(r'[a-z][a-z0-9_]{0,47}',name) and name not in proposed:
                proposed.append(name)
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('value'),str) or not 1 <= len(row['value']) <= 1000 or not any(c.isalnum() for c in row['value']) or row.get('category') not in CATEGORIES or not isinstance(row.get('role'),str):
                rejected += 1
                continue
            evidence = anchor(row, indexed)
            # Each page call may only cite its own page, even if a foreign ID exists.
            if not evidence or any(s['page'] != page['number'] for s in evidence):
                rejected += 1
                continue
            key = (norm(row['value']), row['category'], norm(row['role']))
            item = entities.setdefault(key, {'id':'e-'+hashlib.sha256('|'.join(key).encode()).hexdigest()[:16],
                'value':row['value'], 'category':row['category'], 'role':row['role'][:200], 'evidence':[]})
            exact = precise_evidence(row['value'], evidence, Path(directory)/'source')
            for source in exact:
                if not any(e['id']==source['id'] and e['bbox']==source['bbox'] for e in item['evidence']):
                    item['evidence'].append(source)
    return {'schema_version':'1.0','mode':'nvidia','model':provider.model,
            'document_type':str(outputs[0].get('document_type','Document'))[:150] if outputs else 'Document',
            'summary':str(outputs[0].get('summary',''))[:1500] if outputs else '',
            'suggested_fields':proposed[:12], 'entities':list(entities.values()),
            'pages_analyzed':len(pages), 'page_limit':90, 'pages_at_entity_limit':limits,
            'rejected_unanchored_candidates':rejected,'model_calls':provider.calls,
            'elapsed_seconds':round(time.monotonic()-started,2),
            'limitation':'Model-discovered entities with literal source anchors. Categories and roles are model interpretations, not independently verified. Discovery may miss entities; up to 90 candidates per page.'}
