import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agents.extraction_agent import GEMINI_MODEL
from agents.search_agent import search_identity
from config import settings
from db.supabase_client import log_pipeline_error
from graph import run_pipeline
from schemas.models import PipelineState

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DocuFlow", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = Lock()


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "llm_provider": settings.llm_provider,
        "gemini_model": GEMINI_MODEL,
    }


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type_hint: str | None = Form(None),
) -> dict:
    document_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload.bin").suffix
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = tmp.name
        tmp.write(contents)

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "processing"}
    background_tasks.add_task(
        _run_job, job_id, temp_path, doc_type_hint, document_id
    )
    return {"job_id": job_id, "status": "processing"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


def require_search_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or x_api_key != settings.search_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/search")
def search_documents(
    query: str,
    _: None = Depends(require_search_api_key),
) -> dict:
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    try:
        return search_identity(query.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


def _run_job(
    job_id: str,
    temp_path: str,
    doc_type_hint: str | None,
    document_id: str,
) -> None:
    try:
        state: PipelineState = run_pipeline(
            file_path=temp_path,
            doc_type_hint=doc_type_hint,
            document_id=document_id,
        )
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done",
                "result": state.model_dump(mode="json"),
            }
    except Exception as exc:
        try:
            log_pipeline_error(document_id, str(exc))
        except Exception:
            pass
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "error": str(exc)}
    finally:
        Path(temp_path).unlink(missing_ok=True)
