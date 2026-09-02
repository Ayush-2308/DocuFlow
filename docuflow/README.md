# DocuFlow

Multi-agent document processing pipeline for invoices, receipts, and KYC documents. OCR, field extraction, validation, and categorization are orchestrated with LangGraph and persisted in Supabase.

## Architecture

```
Client
  POST /upload (file + optional doc_type_hint)
        |
        v
   FastAPI (main.py)
        |
        v
   LangGraph pipeline (graph.py)
        |
        +-- intake
        +-- ocr              -> Mistral OCR (agents/ocr_agent.py)
        +-- extraction       -> OpenAI / Anthropic JSON extract (agents/extraction_agent.py)
        +-- validation       -> rule checks + confidence (agents/validation_agent.py)
        |
        +-- if confidence < 0.75 or validation_errors
        |         -> needs_review (terminal)
        |
        +-- categorization   -> keyword rules (agents/categorization_agent.py)
        +-- storage          -> Supabase documents + processed_documents
```

Failed pipeline runs are written to `pipeline_errors` via `log_pipeline_error`.

## Setup

1. Create and activate a virtual environment (from the `docuflow/` directory):

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment variables and fill in real keys:

```bash
copy .env.example .env
# macOS / Linux: cp .env.example .env
```

Required values:

- `SUPABASE_URL`, `SUPABASE_KEY`
- `OCR_API_KEY`, `OCR_ENDPOINT`, `OCR_PROVIDER`
- `LLM_API_KEY`, `LLM_PROVIDER` (`openai`, `anthropic`, or `gemini`)

4. Apply the schema in the Supabase SQL editor:

```bash
# run the contents of db/migrations.sql against your project
```

## Run locally

From the `docuflow/` directory:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open the upload UI at http://127.0.0.1:8000  
API docs stay at http://127.0.0.1:8000/docs

## Example: upload a document

`doc_type_hint` should be `invoice`, `receipt`, or `kyc`.

```bash
curl -X POST "http://127.0.0.1:8000/upload" \
  -F "file=@./sample-invoice.pdf" \
  -F "doc_type_hint=invoice"
```
