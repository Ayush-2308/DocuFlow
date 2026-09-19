import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schemas.models import PipelineState

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "docuflow.sqlite"
_lock = threading.Lock()
_initialized = False

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    doc_type_hint TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_documents (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    doc_type_hint TEXT,
    raw_text TEXT,
    extracted_data TEXT,
    confidence_score REAL,
    validation_errors TEXT NOT NULL DEFAULT '[]',
    category TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents (document_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pipeline_errors (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS processed_documents_document_id_idx
    ON processed_documents (document_id);
CREATE INDEX IF NOT EXISTS pipeline_errors_document_id_idx
    ON pipeline_errors (document_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    global _initialized
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not _initialized:
        conn.executescript(_SCHEMA)
        conn.commit()
        _initialized = True
    return conn


def insert_document(state: PipelineState) -> None:
    now = _now()
    extracted = json.dumps(state.extracted_data or {}, default=str)
    errors = json.dumps(state.validation_errors or [], default=str)
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, file_path, doc_type_hint, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    file_path = excluded.file_path,
                    doc_type_hint = excluded.doc_type_hint,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    state.document_id,
                    state.file_path,
                    state.doc_type_hint,
                    state.status,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO processed_documents (
                    id, document_id, file_path, doc_type_hint, raw_text,
                    extracted_data, confidence_score, validation_errors,
                    category, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    state.document_id,
                    state.file_path,
                    state.doc_type_hint,
                    state.raw_text,
                    extracted,
                    state.confidence_score,
                    errors,
                    state.category,
                    state.status,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def update_document_status(document_id: str, status: str) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE documents
                SET status = ?, updated_at = ?
                WHERE document_id = ?
                """,
                (status, _now(), document_id),
            )
            conn.commit()
        finally:
            conn.close()


def log_pipeline_error(document_id: str, error: str) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO pipeline_errors (id, document_id, error, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), document_id, error, _now()),
            )
            conn.commit()
        finally:
            conn.close()


def list_processed_documents(limit: int = 50) -> list[dict]:
    capped = max(1, min(limit, 200))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT document_id, doc_type_hint, extracted_data, created_at, status, category
                FROM processed_documents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (capped,),
            ).fetchall()
        finally:
            conn.close()
    return [_row_to_processed(row) for row in rows]


def delete_document(document_id: str) -> bool:
    doc_id = (document_id or "").strip()
    if not doc_id:
        return False
    with _lock:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT 1 FROM documents WHERE document_id = ? LIMIT 1",
                (doc_id,),
            ).fetchone()
            processed = conn.execute(
                "SELECT 1 FROM processed_documents WHERE document_id = ? LIMIT 1",
                (doc_id,),
            ).fetchone()
            if not (existing or processed):
                return False
            conn.execute(
                "DELETE FROM processed_documents WHERE document_id = ?", (doc_id,)
            )
            conn.execute("DELETE FROM pipeline_errors WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE document_id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()
    return True


def delete_documents(document_ids: list[str]) -> list[str]:
    deleted: list[str] = []
    for item in document_ids:
        doc_id = (item or "").strip()
        if doc_id and delete_document(doc_id):
            deleted.append(doc_id)
    return deleted


def search_processed_documents(
    name: str,
    doc_type: str | None = None,
) -> list[dict]:
    needle = _safe_ilike_fragment(name)
    if not needle:
        return []
    pattern = f"%{needle.lower()}%"
    sql = """
        SELECT document_id, doc_type_hint, extracted_data, created_at, status, category
        FROM processed_documents
        WHERE (
            LOWER(COALESCE(json_extract(extracted_data, '$.full_name'), '')) LIKE ?
            OR LOWER(COALESCE(json_extract(extracted_data, '$.vendor_name'), '')) LIKE ?
            OR LOWER(COALESCE(json_extract(extracted_data, '$.merchant_name'), '')) LIKE ?
        )
    """
    params: list[Any] = [pattern, pattern, pattern]
    if doc_type in {"invoice", "receipt", "kyc"}:
        sql += " AND LOWER(COALESCE(doc_type_hint, '')) = ?"
        params.append(doc_type)
    sql += " ORDER BY created_at DESC"
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    return [_row_to_processed(row) for row in rows]


def _row_to_processed(row: sqlite3.Row) -> dict:
    extracted = row["extracted_data"]
    if isinstance(extracted, str):
        try:
            extracted = json.loads(extracted)
        except json.JSONDecodeError:
            extracted = {}
    return {
        "document_id": row["document_id"],
        "doc_type_hint": row["doc_type_hint"],
        "extracted_data": extracted if isinstance(extracted, dict) else {},
        "created_at": row["created_at"],
        "status": row["status"],
        "category": row["category"],
    }


def _safe_ilike_fragment(value: str) -> str:
    cleaned = (value or "").strip()
    for char in ("%", "_", ",", "(", ")", "\\"):
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split())
