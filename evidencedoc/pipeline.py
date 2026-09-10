"""Source matching is not semantic truth. All decisions have inspectable evidence."""
import re
import time
import unicodedata
from collections import defaultdict
from .provider import NvidiaProvider, ProviderError
from .schemas import CANDIDATES, DECISIONS, REPAIR

DEFAULT_FIELDS = ["company_name", "company_number", "authorized_person", "signing_rule", "authority_limit", "effective_date", "valid_until"]
ALIASES = {
    "company_name": ["company name", "legal entity", "registered name"],
    "company_number": ["company number", "registration number", "registration no"],
    "authorized_person": ["authorized person", "representative", "signatory"],
    "signing_rule": ["signing rule", "execution rule", "signature rule"],
    "authority_limit": ["authority limit", "transaction limit", "authorized amount"],
    "effective_date": ["effective date", "effective from"],
    "valid_until": ["valid until", "expiry date", "expires on"],
}


def norm(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def literal_match(value, evidence):
    if not isinstance(value, str) or not value.strip():
        return False
    # Do not accept 250 inside 1250 or $1,250 inside $1,250,000.
    needle, haystack = norm(value), norm(evidence)
    for match in re.finditer(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack):
        before, after = haystack[:match.start()], haystack[match.end():]
        if needle[0].isdigit() and re.search(r"\d[.,]$", before):
            continue
        if needle[-1].isdigit() and re.match(r"[.,]\d", after):
            continue
        return True
    return False



def field_value_shape(field, value):
    """A date field needs a calendar expression, not a copied non-date clause.

    This is a format check, not validation of the field's legal/semantic meaning.
    Month-year precision is allowed; no date normalization or inference is done.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    date_field = field.endswith(("_date", "_tarihi")) or field in {"valid_until", "effective_from"}
    if not date_field:
        return True
    text = norm(value)
    months = r"january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık"
    named = re.search(r"\b(?:"+months+r")\b", text) and re.search(r"\b\d{4}\b", text)
    numeric = re.search(r"(?<!\d)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})(?!\d)", text)
    return bool(named or numeric)

def local_candidates(spans, fields):
    result = []
    for field in fields:
        names = ALIASES.get(field, [field.replace("_", " ")])
        for span in spans:
            for name in names:
                m = re.match(r"^\s*" + re.escape(name) + r"\s*[:=]\s*(.+?)\s*$", span["text"], re.I)
                if m:
                    value = m.group(1).strip()
                    if norm(value) not in {"n/a", "not specified", "unknown", "not provided", "-"}:
                        result.append({"field": field, "value": value, "span_ids": [span["id"]]})
                    break
    return result


def anchor(candidate, index):
    ids = candidate.get("span_ids")
    if not isinstance(ids, list) or not ids or len(ids) > 8 or any(not isinstance(i, str) or i not in index for i in ids):
        return []
    sources = [index[i] for i in dict.fromkeys(ids)]
    if any(literal_match(candidate.get("value"), s["text"]) for s in sources):
        return sources
    # A value may wrap over consecutive lines, but never join unrelated locations.
    order = {identifier: i for i, identifier in enumerate(index)}
    ordered = sorted(sources, key=lambda s: order[s["id"]])
    group = []
    for source in ordered:
        if group and (source["page"] != group[-1]["page"] or order[source["id"]] != order[group[-1]["id"]]+1):
            if literal_match(candidate.get("value"), " ".join(s["text"] for s in group)):
                return sources
            group = []
        group.append(source)
    return sources if literal_match(candidate.get("value"), " ".join(s["text"] for s in group)) else []


def run_pipeline(document, fields, mode="local", directory=None, fault_injection=False, provider=None):
    if fault_injection:
        raise ValueError("Injected candidates are disabled; use original document evidence.")
    started = time.monotonic()
    spans = document["spans"]
    index = {s["id"]: s for s in spans}
    events = []
    def event(stage, message, field=None, **extra):
        events.append({"stage": stage, "message": message, "field": field, **extra})
    event("read", f"Read {len(document['pages'])} pages and {len(spans)} source spans.")
    if mode == "nvidia":
        provider = provider or NvidiaProvider()
        response = provider.ask(
            'For each requested field, extract all conflicting literal values. Return {"candidates":[{"field":"field_name",'
            '"value":"exact substring from one or consecutive spans", "span_ids":["source id"]}]}. '
            'Return exactly one top-level candidates array, not an object grouped by field. '
            'Omit fields without evidence. Include contradictory values for the SAME requested field; respect qualifiers such as dates, fiscal periods, roles, current versus previous rates. '
            'Copy the shortest complete value verbatim; do not add units or paraphrase. Cite adjacent context spans to establish the field meaning.',
            {"fields": fields, "date_fields_require_calendar_values": [f for f in fields if f.endswith(("_date", "_tarihi")) or f == "valid_until"], "spans": [{"id": s["id"], "text": s["text"]} for s in spans]}, schema=CANDIDATES)
        candidates = response.get("candidates")
        if not isinstance(candidates, list) or len(candidates) > 100:
            raise ProviderError("Invalid or oversized candidate list from NVIDIA.")
    else:
        candidates = local_candidates(spans, fields)
    candidates = [c for c in candidates if isinstance(c, dict) and isinstance(c.get("field"), str)
                  and c["field"] in fields and isinstance(c.get("value"), str) and len(c["value"]) <= 2000]
    event("extract", f"Produced {len(candidates)} candidates.", model=provider.model if provider else "local-label-parser")
    def nearby(candidate):
        ids = candidate.get("span_ids", [])
        if not isinstance(ids, list):
            return []
        positions = [i for i, span in enumerate(spans) if span["id"] in ids]
        selected = set()
        for position in positions:
            for j in range(max(0, position-2), min(len(spans), position+3)):
                if spans[j]["page"] == spans[position]["page"]:
                    selected.add(j)
        return [{"id": spans[j]["id"], "text": spans[j]["text"]} for j in sorted(selected)]

    approved, rejected = defaultdict(list), defaultdict(list)
    repairs = set()
    retry_budget = 3
    decisions = {}
    normalized_review = {}
    if provider and candidates:
        review = provider.ask('Review every candidate against its cited text. A literal match alone is insufficient. '
            'Check that the text explicitly states the requested field and does not negate it. '
            'Use nearby context to interpret wrapped sentences and roles. Copy each input index exactly, starting at zero. '
            'Return {"decisions":[{"index":0,"supported":true,"reason":"short evidence-based explanation",'
            '"value":"minimal complete literal field value", "span_ids":["source id"]}]}. '
            'For supported candidates, remove redundant labels, role titles on person-name fields, and introductory wording. '
            'Keep explicit measurement units. A monthly cap needs the amount, not the words per month. '
            'Do not treat alternate wording of the SAME value as a conflict. Each normalized value must be an exact substring of cited consecutive lines. '
            'Do not change meaning or substitute a different date/role/value. Distinguish release, implementation, record, signature and expiry dates. '
            'If uncertain, supported must be false and value null.',
            {"candidates": [{"index": i, "field": c["field"], "value": c["value"],
             "nearby_context": nearby(c), "evidence": [index[s]["text"] for s in c.get("span_ids", []) if isinstance(s, str) and s in index]}
              for i, c in enumerate(candidates) if isinstance(c.get("span_ids"), list)]}, schema=DECISIONS)
        for d in review.get("decisions", []) if isinstance(review.get("decisions"), list) else []:
            if isinstance(d, dict) and type(d.get("index")) is int:
                decisions[d["index"]] = d.get("supported") is True
                if d.get("supported") is True and isinstance(d.get("value"), str):
                    normalized_review[d["index"]] = d
                if 0 <= d["index"] < len(candidates):
                    event("review", str(d.get("reason", ""))[:500], candidates[d["index"]]["field"], supported=d.get("supported") is True)
    for i, candidate in enumerate(candidates):
        field = candidate["field"]
        proposed = normalized_review.get(i)
        if proposed and field_value_shape(field, candidate["value"]) and literal_match(proposed["value"], candidate["value"]):
            allowed_ids = {span["id"] for span in nearby(candidate)}
            proposed_ids = proposed.get("span_ids", [])
            normalized_candidate = {"field": field, "value": proposed["value"], "span_ids": proposed_ids}
            if (isinstance(proposed_ids, list) and all(isinstance(s, str) and s in allowed_ids for s in proposed_ids)
                    and field_value_shape(field, proposed["value"]) and anchor(normalized_candidate, index)):
                if proposed["value"] != candidate["value"]:
                    event("normalize", "Semantic review returned a minimal value anchored to the same source region.", field,
                          before=candidate["value"], after=proposed["value"])
                candidate = normalized_candidate
        shape_valid = field_value_shape(field, candidate["value"])
        sources = anchor(candidate, index) if shape_valid else []
        semantic = decisions.get(i, False) if provider else True
        if not sources and semantic and provider and shape_valid:
            context_ids = [span["id"] for span in nearby(candidate)]
            if len(context_ids) <= 8:
                sources = anchor({"value": candidate["value"], "span_ids": context_ids}, index)
                if sources:
                    repairs.add(field)
                    event("repair", "Recovered the citation from adjacent source lines after semantic review.", field,
                          before=candidate["value"], after=candidate["value"])
        if not sources or not semantic:
            reason = ("Candidate is empty; there is no value to verify." if not candidate["value"].strip() else "The requested date field requires a calendar date, not an incomplete fragment or non-date phrase.") if not shape_valid else "Candidate is not a literal match in its cited source." if not sources else "Semantic review did not support this field/value."
            event("reject", reason, field, candidate=candidate["value"])
            rejected[field].append(candidate["value"])
            ids = candidate.get("span_ids", [])
            source = next((index[s] for s in ids if isinstance(s, str) and s in index), None) if isinstance(ids, list) else None
            if source and retry_budget and shape_valid:
                retry_budget -= 1
                event("retry", "Re-read the cited region." if provider else "Re-parse the labeled source line locally.", field)
                if provider:
                    center = next(j for j, span in enumerate(spans) if span["id"] == source["id"])
                    region = [span for span in spans[max(0,center-2):center+3] if span["page"] == source["page"]]
                    region_box = [min(span["bbox"][0] for span in region), min(span["bbox"][1] for span in region),
                                  max(span["bbox"][2] for span in region), max(span["bbox"][3] for span in region)]
                    repair = provider.ask('Read this document crop and the source text. Extract only the requested field. '
                        'Return {"value":"literal value", "supported":true} or {"value":null,"supported":false}. '
                        'Both image and source text must support it.', {"field": field, "source_text": " ".join(span["text"] for span in region)},
                        image_path=directory / f"page-{source['page']}.png", bbox=region_box, schema=REPAIR)
                    options = [{"field": field, "value": repair.get("value"), "span_ids": [span["id"] for span in region]}] if repair.get("supported") is True else []
                else:
                    options = local_candidates([source], [field])
                for repaired in options:
                    evidence = anchor(repaired, index)
                    if evidence and field_value_shape(field, repaired.get("value")):
                        approved[field].append((repaired["value"], evidence))
                        repairs.add(field)
                        event("repair", "Recovered a source-supported value.", field,
                              before=candidate["value"], after=repaired["value"])
            continue
        approved[field].append((candidate["value"], sources))
    # Preserve explicitly labeled contradictions the model may have omitted.
    for candidate in local_candidates(spans, fields):
        field = candidate["field"]
        if not field_value_shape(field, candidate["value"]):
            continue
        if approved[field] and all(norm(v) != norm(candidate["value"]) for v, _ in approved[field]):
            # A label parser sees only the first line of a wrapped value. Do not
            # invent a conflict when adjacent source lines prove its continuation.
            start = next(j for j, span in enumerate(spans) if span["id"] == candidate["span_ids"][0])
            continuation = [span["id"] for span in spans[start:start+8] if span["page"] == spans[start]["page"]]
            if any(norm(v).startswith(norm(candidate["value"])+" ") and
                   anchor({"value": v, "span_ids": continuation}, index) for v, _ in approved[field]):
                continue
            approved[field].append((candidate["value"], anchor(candidate, index)))
            event("conflict", "Found another explicitly labeled value in the document.", field)
    results = []
    for field in fields:
        unique = {}
        for value, evidence in approved[field]:
            key = norm(value)
            if key not in unique:
                unique[key] = {"value": value, "evidence": []}
            existing = {s["id"] for s in unique[key]["evidence"]}
            unique[key]["evidence"].extend(s for s in evidence if s["id"] not in existing)
        options = list(unique.values())
        status = "conflict" if len(options) > 1 else ("recovered" if field in repairs else "grounded") if options else "abstained"
        evidence = [s for o in options for s in o["evidence"]]
        results.append({"field": field, "status": status, "value": options[0]["value"] if len(options) == 1 else None,
                        "evidence": evidence, "alternatives": options if len(options) > 1 else [],
                        "rejected_candidates": rejected[field], "confidence": None,
                        "verification": "nemotron-review+literal-match" if provider else "label-rule+literal-match",
                        "reason": "Multiple source-supported values require human review." if len(options) > 1 else
                        "Literal source support found; review the cited context." if options else
                        "No sufficiently supported value. This does not prove the field is absent."})
    counts = {s: sum(f["status"] == s for f in results) for s in ["grounded", "recovered", "conflict", "abstained"]}
    event("coverage", f"{counts['grounded']+counts['recovered']} of {len(fields)} fields resolved; {counts['conflict']} conflicts; {counts['abstained']} abstentions.")
    return {"fields": results, "events": events, "counts": counts, "requested": len(fields), "mode": mode,
            "model": provider.model if provider else None, "model_calls": provider.calls if provider else [],
            "fault_injection": fault_injection, "elapsed_seconds": round(time.monotonic()-started, 3),
            "confidence_note": "Confidence is null: no calibrated probability model has been evaluated.",
            "limitations": "Source support is not a guarantee of semantic correctness. OCR and correlated model errors remain possible."}
