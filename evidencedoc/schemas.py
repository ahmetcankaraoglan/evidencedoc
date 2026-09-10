"""Bounded output structures, independent of document answers."""
def object_schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

CANDIDATES = object_schema({"candidates": {"type": "array", "items": object_schema({
    "field": {"type": "string"}, "value": {"type": "string"},
    "span_ids": {"type": "array", "items": {"type": "string"}}})}})
DECISIONS = object_schema({"decisions": {"type": "array", "items": object_schema({
    "index": {"type": "integer"}, "supported": {"type": "boolean"}, "reason": {"type": "string"},
    "value": {"type": ["string", "null"]}, "span_ids": {"type": "array", "items": {"type": "string"}}})}})
REPAIR = object_schema({"value": {"type": ["string", "null"]}, "supported": {"type": "boolean"}})
