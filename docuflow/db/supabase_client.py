import socket
from urllib.parse import urlparse

from supabase import Client, create_client

from config import settings
from db import sqlite_store
from schemas.models import PipelineState

_use_supabase: bool | None = None
_supabase: Client | None = None


def storage_backend() -> str:
    return "supabase" if _supabase_enabled() else "sqlite"


def _hostname_resolves(url: str) -> bool:
    host = urlparse((url or "").strip()).hostname
    if not host:
        return False
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return True
    except OSError:
        return False


def _is_unreachable_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    markers = (
        "name or service not known",
        "getaddrinfo failed",
        "nodename nor servname",
        "temporary failure in name resolution",
        "errno -2",
        "errno 11001",
        "failed to resolve",
        "name resolution",
    )
    return any(marker in text for marker in markers)


def _supabase_enabled() -> bool:
    global _use_supabase
    if _use_supabase is None:
        _use_supabase = _hostname_resolves(settings.supabase_url)
    return _use_supabase


def _disable_supabase() -> None:
    global _use_supabase, _supabase
    _use_supabase = False
    _supabase = None


def _client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase


def _raise_if_error(result: object, action: str) -> None:
    error = getattr(result, "error", None)
    if error:
        raise RuntimeError(f"Supabase {action} failed: {error}")


def _run(supabase_call, sqlite_call):
    if _supabase_enabled():
        try:
            return supabase_call()
        except Exception as exc:
            if not _is_unreachable_error(exc):
                raise
            _disable_supabase()
    return sqlite_call()


def insert_document(state: PipelineState) -> None:
    """Insert a documents row and a processed_documents snapshot from pipeline state."""

    def supabase_call() -> None:
        supabase = _client()
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
            supabase.table("documents")
            .upsert(document_row, on_conflict="document_id")
            .execute()
        )
        _raise_if_error(documents_result, "insert documents")
        processed_result = supabase.table("processed_documents").insert(processed_row).execute()
        _raise_if_error(processed_result, "insert processed_documents")

    _run(supabase_call, lambda: sqlite_store.insert_document(state))


def update_document_status(document_id: str, status: str) -> None:
    """Update the status of an existing documents row."""

    def supabase_call() -> None:
        result = (
            _client()
            .table("documents")
            .update({"status": status})
            .eq("document_id", document_id)
            .execute()
        )
        _raise_if_error(result, "update document status")

    _run(
        supabase_call,
        lambda: sqlite_store.update_document_status(document_id, status),
    )


def log_pipeline_error(document_id: str, error: str) -> None:
    """Append an error message for a document to pipeline_errors."""

    def supabase_call() -> None:
        result = (
            _client()
            .table("pipeline_errors")
            .insert({"document_id": document_id, "error": error})
            .execute()
        )
        _raise_if_error(result, "log pipeline error")

    _run(
        supabase_call,
        lambda: sqlite_store.log_pipeline_error(document_id, error),
    )


def list_processed_documents(limit: int = 50) -> list[dict]:
    """Return recent processed document rows for the delete UI."""

    def supabase_call() -> list[dict]:
        result = (
            _client()
            .table("processed_documents")
            .select(
                "document_id, doc_type_hint, extracted_data, created_at, status, category"
            )
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 200)))
            .execute()
        )
        _raise_if_error(result, "list processed_documents")
        return list(result.data or [])

    return _run(
        supabase_call,
        lambda: sqlite_store.list_processed_documents(limit),
    )


def delete_document(document_id: str) -> bool:
    """Remove a document from all tables. Returns True if a matching row existed."""

    def supabase_call() -> bool:
        doc_id = (document_id or "").strip()
        if not doc_id:
            return False
        supabase = _client()
        existing = (
            supabase.table("documents")
            .select("document_id")
            .eq("document_id", doc_id)
            .limit(1)
            .execute()
        )
        _raise_if_error(existing, "lookup documents")
        processed = (
            supabase.table("processed_documents")
            .select("document_id")
            .eq("document_id", doc_id)
            .limit(1)
            .execute()
        )
        _raise_if_error(processed, "lookup processed_documents")
        if not (existing.data or processed.data):
            return False

        processed_result = (
            supabase.table("processed_documents")
            .delete()
            .eq("document_id", doc_id)
            .execute()
        )
        _raise_if_error(processed_result, "delete processed_documents")
        errors_result = (
            supabase.table("pipeline_errors")
            .delete()
            .eq("document_id", doc_id)
            .execute()
        )
        _raise_if_error(errors_result, "delete pipeline_errors")
        documents_result = (
            supabase.table("documents").delete().eq("document_id", doc_id).execute()
        )
        _raise_if_error(documents_result, "delete documents")
        return True

    return _run(
        supabase_call,
        lambda: sqlite_store.delete_document(document_id),
    )


def delete_documents(document_ids: list[str]) -> list[str]:
    """Delete documents by id. processed_documents rows cascade from documents."""

    def supabase_call() -> list[str]:
        ids = list(dict.fromkeys(item.strip() for item in document_ids if item and item.strip()))
        if not ids:
            return []
        supabase = _client()
        existing = (
            supabase.table("documents").select("document_id").in_("document_id", ids).execute()
        )
        _raise_if_error(existing, "lookup documents for delete")
        found = [
            str(row.get("document_id"))
            for row in (existing.data or [])
            if row.get("document_id")
        ]
        if not found:
            return []
        errors_result = (
            supabase.table("pipeline_errors").delete().in_("document_id", found).execute()
        )
        _raise_if_error(errors_result, "delete pipeline_errors")
        documents_result = (
            supabase.table("documents").delete().in_("document_id", found).execute()
        )
        _raise_if_error(documents_result, "delete documents")
        return found

    return _run(supabase_call, lambda: sqlite_store.delete_documents(document_ids))


def search_processed_documents(
    name: str,
    doc_type: str | None = None,
) -> list[dict]:
    """Case-insensitive partial match on name fields inside extracted_data JSONB."""

    def supabase_call() -> list[dict]:
        needle = _safe_ilike_fragment(name)
        if not needle:
            return []
        pattern = f"%{needle}%"
        query = (
            _client()
            .table("processed_documents")
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

    return _run(
        supabase_call,
        lambda: sqlite_store.search_processed_documents(name, doc_type),
    )


def _safe_ilike_fragment(value: str) -> str:
    cleaned = (value or "").strip()
    for char in ("%", "_", ",", "(", ")", "\\"):
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split())
