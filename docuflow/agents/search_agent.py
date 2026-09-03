from typing import Any

from agents.extraction_agent import ExtractionError, _call_llm, _parse_json_object
from db.supabase_client import search_processed_documents
from utils.sanitize import sanitize_response

INTENT_PROMPT = """Parse this document-search request into JSON only.
Keys:
- name: the person or business name to look up (string, required)
- doc_type: one of invoice, receipt, kyc, or null if unspecified
- latest: true if they want only the most recent matching document, else false

User query:
{query}
"""

def parse_search_intent(query: str) -> dict[str, Any]:
    """Turn free text into {name, doc_type, latest}. Falls back to using the raw query as name."""
    fallback = {"name": query.strip(), "doc_type": None, "latest": False}
    if not query.strip():
        return fallback
    if _is_plain_name(query):
        return fallback
    try:
        raw = _call_llm(INTENT_PROMPT.replace("{query}", query.strip()))
        parsed, _error = _parse_json_object(raw)
        if parsed is None:
            return fallback
        name = str(parsed.get("name") or query).strip() or query.strip()
        doc_type = parsed.get("doc_type")
        if isinstance(doc_type, str):
            doc_type = doc_type.strip().lower()
            if doc_type not in {"invoice", "receipt", "kyc"}:
                doc_type = None
        else:
            doc_type = None
        latest = bool(parsed.get("latest"))
        return {"name": name, "doc_type": doc_type, "latest": latest}
    except (ExtractionError, TypeError, ValueError):
        return fallback


def _is_plain_name(query: str) -> bool:
    lowered = query.strip().lower()
    cues = (
        "show",
        "find",
        "last",
        "latest",
        "invoice",
        "receipt",
        "kyc",
        "aadhaar",
        "aadhar",
        "pan",
        "passport",
    )
    if any(cue in lowered for cue in cues):
        return False
    return len(query.split()) <= 4


def search_identity(query: str) -> dict[str, Any]:
    """Search stored documents for an identity and return masked records."""
    intent = parse_search_intent(query)
    rows = search_processed_documents(intent["name"], intent.get("doc_type"))
    if intent.get("latest") and rows:
        rows = [rows[0]]

    type_order = {"kyc": 0, "invoice": 1, "receipt": 2}
    results: list[dict[str, Any]] = []
    for row in rows:
        doc_type = _normalize_doc_type(row.get("doc_type_hint"))
        data = row.get("extracted_data")
        if not isinstance(data, dict):
            data = {}
        results.append(
            {
                "document_type": doc_type,
                "document_id": row.get("document_id"),
                "data": sanitize_response(data),
            }
        )
    results.sort(key=lambda item: type_order.get(item["document_type"], 9))
    return {"query": query, "results": results}


def _normalize_doc_type(hint: Any) -> str:
    key = str(hint or "").strip().lower().replace(" ", "_")
    if key in {"kyc", "kycdocument", "kyc_document"}:
        return "kyc"
    if key in {"invoice", "receipt"}:
        return key
    return key or "unknown"
