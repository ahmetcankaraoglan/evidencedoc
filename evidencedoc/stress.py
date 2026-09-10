"""Counterfactual source removal. Original documents and results remain immutable.

Both text and rendered pages are masked before a fresh extraction. The previous
answer is never part of the extraction prompt. This tests source dependence,
not factual correctness or calibrated confidence.
"""
import copy
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .pipeline import norm, run_pipeline


def overlaps(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def mask_document(document, selected_ids, source_dir, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = [s for s in document['spans'] if s['id'] in selected_ids]
    if not selected or len(selected) != len(set(selected_ids)):
        raise ValueError('Select valid evidence spans from this document.')
    # The padding covers anti-aliased glyph edges. Also remove overlapping text
    # spans so a text-layer alias cannot reveal the masked region.
    masks = {}
    for s in selected:
        b = s['bbox']
        masks.setdefault(s['page'], []).append([max(0,b[0]-.002), max(0,b[1]-.002),
                                                min(1,b[2]+.002), min(1,b[3]+.002)])
    removed = [s for s in document['spans'] if any(overlaps(s['bbox'], b) for b in masks.get(s['page'], []))]
    removed_ids = {s['id'] for s in removed}
    masked = copy.deepcopy(document)
    masked['spans'] = [s for s in masked['spans'] if s['id'] not in removed_ids]
    # Strip metadata: no filename/previous result is supplied to the model.
    masked = {'pages': masked['pages'], 'spans': masked['spans']}
    for page in document['pages']:
        n = page['number']
        with Image.open(Path(source_dir) / f'page-{n}.png') as src:
            image = src.convert('RGB')
            draw = ImageDraw.Draw(image)
            for s in removed:
                if s['page'] == n:
                    x0,y0,x1,y1 = s['bbox']
                    draw.rectangle((max(0,int(x0*image.width)-3), max(0,int(y0*image.height)-3),
                                    min(image.width,int(x1*image.width)+3), min(image.height,int(y1*image.height)+3)),
                                   fill='#202d32')
            image.save(output_dir / f'page-{n}.png')
    (output_dir / 'masked-document.json').write_text(json.dumps(masked, ensure_ascii=False))
    return masked, removed


def run_stress(original, field_name, selected_ids, source_dir, output_dir, provider=None):
    field = next((f for f in original['fields'] if f['field'] == field_name), None)
    if not field or not field.get('value') or not field.get('evidence'):
        raise ValueError('Choose a field with an answer and source evidence.')
    allowed = {s['id'] for s in field['evidence']}
    if not selected_ids or not set(selected_ids) <= allowed:
        raise ValueError('Only cited evidence for this field can be withheld.')
    masked, removed = mask_document(original['document'], selected_ids, source_dir, output_dir)
    result = run_pipeline(masked, [field_name], original['mode'], Path(output_dir), provider=provider)
    after = result['fields'][0]
    if after['status'] == 'conflict':
        outcome = 'conflict'
    elif after['value'] is None:
        outcome = 'withdrew'
    elif norm(after['value']) == norm(field['value']):
        outcome = 'alternative_support'
    else:
        outcome = 'changed'
    payload = {
        'schema_version': '1.0', 'kind': 'source-removal-experiment',
        'source_sha256': original['document']['sha256'],
        'source_document_id': original['document']['id'], 'field': field_name,
        'before': field, 'after': after, 'outcome': outcome,
        'removed_spans': removed, 'requested_span_ids': selected_ids,
        'remaining_spans': len(masked['spans']), 'mode': original['mode'],
        'model': result['model'], 'model_calls': result['model_calls'],
        'events': result['events'], 'elapsed_seconds': result['elapsed_seconds'],
        'method': 'Fresh extraction with selected evidence and overlapping text removed. Matching page regions are blacked out before any visual retry. The previous answer is not supplied to the model.',
        'limitation': 'Tests dependence on selected evidence, not truth. Unmasked duplicate evidence may support the same answer. ' + ('The same model family is used; this is not an independent expert review.' if original['mode'] == 'nvidia' else 'Local mode uses deterministic label parsing, with no model calls.')
    }
    payload['experiment_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload
