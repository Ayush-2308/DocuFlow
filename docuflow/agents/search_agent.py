import re
from typing import Any

from agents.extraction_agent import ExtractionError, _call_llm, _parse_json_object
from db.supabase_client import search_processed_documents
from utils.sanitize import sanitize_response

_DOC_WORDS = {
    "kyc": "kyc",
    "kycdocument": "kyc",
    "aadhaar": "kyc",
    "aadhar": "kyc",
    "pan": "kyc",
    "passport": "kyc",
    "invoice": "invoice",
    "invoices": "invoice",
    "receipt": "receipt",
    "receipts": "receipt",
}
_SKIP_WORDS = {
    "show",
    "find",
    "me",
    "my",
    "the",
    "last",
    "latest",
    "of",
    "for",
    "a",
    "an",
    "document",
    "doc",
    "pdf",
    "file",
    "card",
}

INTENT_PROMPT = """Parse this document-search request into JSON only.
Keys:
- name: the person or business name to look up (string, required)
- doc_type: one of invoice, receipt, kyc, or null if unspecified
- latest: true if they want only the most recent matching document, else false

User query:
{query}
"""

def parse_search_intent(query: str) -> dict[str, Any]:
    """Turn free text into {name, doc_type, latest}.

    Short queries and anything that names a document type are parsed locally.
    That keeps "aadhaar", "kyc_pan", and a person's name from being rewritten
    into a business name that only matches invoices.
    """
    cleaned = query.strip()
    local = _local_intent(cleaned)
    if not cleaned:
        return local
    if local["doc_type"] or len(cleaned.split()) <= 6:
        return local
    try:
        raw = _call_llm(INTENT_PROMPT.replace("{query}", cleaned))
        parsed, _error = _parse_json_object(raw)
        if parsed is None:
            return local
        name = str(parsed.get("name") or local["name"] or cleaned).strip()
        doc_type = parsed.get("doc_type")
        if isinstance(doc_type, str):
            doc_type = doc_type.strip().lower()
            if doc_type not in {"invoice", "receipt", "kyc"}:
                doc_type = local["doc_type"]
        else:
            doc_type = local["doc_type"]
        latest = bool(parsed.get("latest")) or local["latest"]
        return {"name": name, "doc_type": doc_type, "latest": latest}
    except (ExtractionError, TypeError, ValueError):
        return local


def _local_intent(query: str) -> dict[str, Any]:
    normalized = query.replace("'s", " ").replace("’s", " ")
    tokens = re.findall(r"[A-Za-z0-9]+", normalized)
    lowered = [token.lower() for token in tokens]
    doc_type = None
    for token in lowered:
        if token in _DOC_WORDS:
            doc_type = _DOC_WORDS[token]
    name_tokens = [
        token
        for token, low in zip(tokens, lowered)
        if low not in _DOC_WORDS and low not in _SKIP_WORDS
    ]
    return {
        "name": " ".join(name_tokens),
        "doc_type": doc_type,
        "latest": any(token in {"last", "latest"} for token in lowered),
    }


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
                "data": sanitize_response(data, doc_hint=doc_type),
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
