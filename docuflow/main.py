import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db.supabase_client import log_pipeline_error
from graph import run_pipeline
from schemas.models import PipelineState
from agents.extraction_agent import GEMINI_MODEL
from config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DocuFlow", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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


@app.post("/upload", response_model=PipelineState)
async def upload(
    file: UploadFile = File(...),
    doc_type_hint: str | None = Form(None),
) -> PipelineState:
    document_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload.bin").suffix
    temp_path: str | None = None

    try:
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            contents = await file.read()
            if not contents:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            tmp.write(contents)

        return run_pipeline(
            file_path=temp_path,
            doc_type_hint=doc_type_hint,
            document_id=document_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        try:
            log_pipeline_error(document_id, str(exc))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
