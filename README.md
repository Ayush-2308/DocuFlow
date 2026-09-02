# DocuFlow

Multi-agent **document automation** pipeline: OCR → LLM extraction → validation → category → Supabase.

Upload an invoice, receipt, or KYC PDF/image. The app returns structured fields (or sends the doc to review) and stores successful runs in the database.

| | |
|---|---|
| **Live demo** | https://docuflow-gbh3.onrender.com |
| **Full documentation** | [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) |
| **API (Swagger)** | https://docuflow-gbh3.onrender.com/docs |

## What it does

```
Upload → OCR (Mistral) → Extract JSON (Gemini/OpenAI/Anthropic)
      → Validate → if low confidence: needs_review
                 → else: categorize → save to Supabase
```

## Tech

Python, FastAPI, LangGraph, Pydantic, Supabase, static HTML UI.

## Run locally

See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md#13-local-setup) — app lives in `docuflow/`.

```bash
cd docuflow
pip install -r requirements.txt
cp .env.example .env   # add real keys
uvicorn main:app --host 127.0.0.1 --port 8000
```

Never commit `.env`. Keys go in local `.env` or the host’s environment variables (e.g. Render).
