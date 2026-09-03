from supabase import Client, create_client

from config import settings
from schemas.models import PipelineState

supabase: Client = create_client(settings.supabase_url, settings.supabase_key)


def insert_document(state: PipelineState) -> None:
    """Insert a documents row and a processed_documents snapshot from pipeline state."""
    document_row = {
        "document_id": state.document_id,
        "file_path": state.file_path,
        "doc_type_hint": state.doc_type_hint,
        "status": state.status,
    }
    processed_row = {
        "document_id": state.document_id,
        "file_path": state.file_path,
        "doc_type_hint": state.doc_type_hint,
        "raw_text": state.raw_text,
        "extracted_data": state.extracted_data,
        "confidence_score": state.confidence_score,
        "validation_errors": state.validation_errors,
        "category": state.category,
        "status": state.status,
    }

    documents_result = (
        supabase.table("documents").upsert(document_row, on_conflict="document_id").execute()
    )
    _raise_if_error(documents_result, "insert documents")

    processed_result = supabase.table("processed_documents").insert(processed_row).execute()
    _raise_if_error(processed_result, "insert processed_documents")


def update_document_status(document_id: str, status: str) -> None:
    """Update the status of an existing documents row."""
    result = (
        supabase.table("documents")
        .update({"status": status})
        .eq("document_id", document_id)
        .execute()
    )
    _raise_if_error(result, "update document status")


def log_pipeline_error(document_id: str, error: str) -> None:
    """Append an error message for a document to pipeline_errors."""
    result = (
        supabase.table("pipeline_errors")
        .insert({"document_id": document_id, "error": error})
        .execute()
    )
    _raise_if_error(result, "log pipeline error")


def search_processed_documents(
    name: str,
    doc_type: str | None = None,
) -> list[dict]:
    """Case-insensitive partial match on name fields inside extracted_data JSONB."""
    needle = _safe_ilike_fragment(name)
    if not needle:
        return []

    pattern = f"%{needle}%"
    query = (
        supabase.table("processed_documents")
        .select(
            "document_id, doc_type_hint, extracted_data, created_at, status, category"
        )
        .or_(
            f"extracted_data->>full_name.ilike.{pattern},"
            f"extracted_data->>vendor_name.ilike.{pattern},"
            f"extracted_data->>merchant_name.ilike.{pattern}"
        )
        .order("created_at", desc=True)
    )
    if doc_type in {"invoice", "receipt", "kyc"}:
        query = query.ilike("doc_type_hint", doc_type)

    result = query.execute()
    _raise_if_error(result, "search processed_documents")
    return list(result.data or [])


def _safe_ilike_fragment(value: str) -> str:
    cleaned = (value or "").strip()
    for char in ("%","_", ",", "(", ")", "\\"):
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split())


def _raise_if_error(result: object, action: str) -> None:
    error = getattr(result, "error", None)
    if error:
        raise RuntimeError(f"Supabase {action} failed: {error}")
