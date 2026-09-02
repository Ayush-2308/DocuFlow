# DocuFlow — Full Documentation

This document describes **what DocuFlow is**, **what was built**, **how each part works**, and **how to run / deploy it**.

| | |
|---|---|
| **Live UI** | https://docuflow-gbh3.onrender.com |
| **Source** | https://github.com/Ayush-2308/DocuFlow |
| **API docs (Swagger)** | `/docs` on the same host |

---

## 1. What the project does

DocuFlow is a **multi-agent document automation pipeline**, exposed as a **web app + HTTP API**.

A user uploads a PDF or image (invoice, receipt, or KYC). The system:

1. Reads text from the file (**OCR** — Mistral).
2. Turns that text into structured JSON (**LLM extraction** — Gemini / OpenAI / Anthropic).
3. Checks required fields, dates, totals, and ID formats (**validation** — rules).
4. If quality is low, stops for **human review**.
5. Otherwise assigns a **category** and **saves** the record in **Supabase**.

It is **not** a chat bot. Inside: specialized agents. Outside: an API and a simple upload UI.

---

## 2. Problem it solves

Manually copying vendor names, invoice totals, or Aadhaar/PAN fields from PDFs is slow and error-prone. DocuFlow automates:

- ingest → extract → validate → route → store  

Other apps can call the API or read Supabase instead of parsing PDFs themselves.

---

## 3. Tech stack

| Layer | Choice |
|--------|--------|
| Language | Python 3.12+ (Render may use 3.14) |
| API / UI host | FastAPI + Uvicorn |
| Orchestration | LangGraph `StateGraph` |
| Schemas | Pydantic v2 |
| OCR | Mistral OCR HTTP API |
| Extraction LLM | Configurable: `gemini`, `openai`, `anthropic` |
| Database | Supabase (Postgres) |
| Frontend | Static HTML / CSS / JS (no React build) |
| Config | `python-dotenv` + environment variables |
| HTTP clients | `httpx` |

---

## 4. Repository layout

```
DocuFlow/
├── README.md                 # Short project overview (GitHub homepage)
├── docs/DOCUMENTATION.md     # This file
├── render.yaml               # Render deploy hints
├── .gitignore                # Ignores .env, venv, caches
└── docuflow/                 # Application root (run uvicorn from here)
    ├── main.py               # FastAPI app, jobs, static UI
    ├── graph.py              # LangGraph pipeline
    ├── config.py             # Loads required env vars
    ├── requirements.txt
    ├── Procfile
    ├── .env.example          # Placeholder keys (commit this, never .env)
    ├── schemas/
    │   └── models.py         # Invoice, Receipt, KYC, PipelineState
    ├── agents/
    │   ├── ocr_agent.py
    │   ├── extraction_agent.py
    │   ├── validation_agent.py
    │   └── categorization_agent.py
    ├── db/
    │   ├── supabase_client.py
    │   └── migrations.sql
    └── static/               # Upload UI
        ├── index.html
        ├── styles.css
        └── app.js
```

**Secrets:** `docuflow/.env` is gitignored. Only `.env.example` is on GitHub.

---

## 5. End-to-end flow (user → result)

```
Browser UI  ──POST /upload (file + doc_type_hint)──► FastAPI
                                                      │
                                                      ├─ save temp file
                                                      ├─ return { job_id, status: processing }   ◄── HTTP ends quickly
                                                      │
                                                      └─ background thread: run_pipeline()
                                                                │
                         LangGraph: intake → ocr → extraction → validation
                                                                │
                                    score < 0.75 or errors? ────┤
                                    yes → needs_review → END    │
                                    no  → categorize → storage (Supabase) → END
                                                                │
Browser polls GET /jobs/{job_id} every 2s until done | error
                                                                │
UI renders status, category, confidence, extracted fields
```

**Why background jobs?** Hosts like Render close long HTTP requests (~30–100s). OCR + LLM often take longer. Upload returns immediately; the UI polls until the pipeline finishes (up to 5 minutes).

---

## 6. Pipeline state (`PipelineState`)

Shared state for every graph node (`schemas/models.py`):

| Field | Meaning |
|--------|---------|
| `document_id` | UUID for this run |
| `file_path` | Temp path of the uploaded file |
| `doc_type_hint` | `invoice` / `receipt` / `kyc` |
| `raw_text` | OCR output |
| `extracted_data` | Validated JSON dict |
| `confidence_score` | 0–1 from validation |
| `validation_errors` | List of rule failures |
| `category` | e.g. Travel Expense, Identity Verification |
| `status` | `pending` → `intake` → `ocr` → `extracted` → `validated` → `categorized` / `needs_review` / `stored` |

---

## 7. Agents — what each one does

### 7.1 OCR (`agents/ocr_agent.py`)

- **Input:** local file path  
- **Output:** extracted text (markdown from pages joined)  
- **How:** Base64 data URL to Mistral `POST {OCR_ENDPOINT}` (`https://api.mistral.ai/v1/ocr`)  
- PDFs → `document_url` + `application/pdf`  
- Images → `image_url` + MIME from extension (png, jpg, webp, …)  
- Failures raise `OCRError` (missing file, HTTP error, empty text)

### 7.2 Extraction (`agents/extraction_agent.py`)

- **Input:** `raw_text`, `doc_type_hint`  
- **Output:** dict matching `Invoice`, `Receipt`, or `KYCDocument`  
- **How:** Builds a prompt with the Pydantic JSON schema; LLM must return JSON only  
- Parses JSON (strips markdown fences); `model_validate`  
- If invalid, **one correction prompt** with the error, then retry  
- **Providers** (`LLM_PROVIDER`):
  - `openai` — Chat Completions  
  - `anthropic` — Messages API  
  - `gemini` / `google` — `generateContent`; retries on 429/503; fallback models `gemini-3.6-flash` then `gemini-2.5-flash`

### 7.3 Validation (`agents/validation_agent.py`)

- **Input:** extracted dict + doc type  
- **Output:** `(confidence_score, error_list)`  
- **Rules:**
  - Required fields present  
  - Dates parse and are not in the future  
  - Invoices: line amounts vs subtotal / tax / total (tolerance `0.05`)  
  - KYC `id_number`: Aadhaar 12 digits, PAN `ABCDE1234F`, Passport `A1234567`  
- Confidence ≈ `1 - failed_checks / total_checks`

### 7.4 Categorization (`agents/categorization_agent.py`)

- Keyword match on vendor/merchant name and item descriptions  
- KYC always → `Identity Verification`  
- Else Travel, Office Supplies, Meals, Software, or `Uncategorized`  
- TODO in code: replace with an LLM later  

### 7.5 Storage (`db/supabase_client.py`)

- `insert_document` — upsert `documents`, insert `processed_documents`  
- `update_document_status` — set `documents.status`  
- `log_pipeline_error` — append to `pipeline_errors`  

Called from the **storage** graph node. Failures during the job also try `log_pipeline_error`.

---

## 8. LangGraph (`graph.py`)

Nodes in order:

`intake` → `ocr` → `extraction` → `validation` → **branch**

- If `validation_errors` is non-empty **or** `confidence_score < 0.75` (or score is `None`) → `needs_review` → END (no category, no Supabase insert).  
- Else → `categorization` → `storage` → END  

`run_pipeline(file_path, doc_type_hint, document_id=None)` builds initial `PipelineState` and `invoke`s the compiled graph.

---

## 9. HTTP API (`main.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Upload UI |
| `GET` | `/static/*` | CSS/JS |
| `GET` | `/health` | Provider + Gemini model name |
| `GET` | `/docs` | Swagger (FastAPI built-in) |
| `POST` | `/upload` | Multipart `file` + optional `doc_type_hint` → `{ job_id, status: "processing" }` |
| `GET` | `/jobs/{job_id}` | `{ status: processing }` or `{ status: done, result: PipelineState }` or `{ status: error, error: "..." }` |

`doc_type_hint` values: `invoice`, `receipt`, `kyc` (case-insensitive in agents).

---

## 10. Database (`db/migrations.sql`)

Run once in the Supabase SQL editor.

- **documents** — id, path, type hint, status  
- **processed_documents** — full snapshot including `extracted_data` JSONB  
- **pipeline_errors** — error strings per `document_id`  

---

## 11. Frontend (`static/`)

- Drag-and-drop or file picker  
- Document type dropdown  
- `POST /upload` then poll `/jobs/{id}` every 2 seconds  
- Shows chips (status, category, confidence), extracted fields, validation errors, collapsible OCR text and raw JSON  

---

## 12. Environment variables

Copy `docuflow/.env.example` → `docuflow/.env` locally. On Render, set the same names in **Environment**.

| Variable | Role |
|----------|------|
| `SUPABASE_URL` | Project URL `https://….supabase.co` |
| `SUPABASE_KEY` | Server key (`sb_secret_…` or service_role JWT) |
| `OCR_API_KEY` | Mistral API key |
| `OCR_ENDPOINT` | `https://api.mistral.ai/v1/ocr` |
| `OCR_PROVIDER` | `mistral` |
| `LLM_API_KEY` | Gemini / OpenAI / Anthropic key |
| `LLM_PROVIDER` | `gemini` \| `openai` \| `anthropic` |

`config.py` **fails at import** if any are missing (that is why Render crashed before env vars were added).

---

## 13. Local setup

```bash
cd docuflow
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # then fill real keys
# Run migrations.sql in Supabase
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 (UI) and http://127.0.0.1:8000/docs (API).

---

## 14. Deploy (Render)

1. Connect GitHub repo `Ayush-2308/DocuFlow`.  
2. **Root Directory:** `docuflow`  
3. **Build:** `pip install -r requirements.txt`  
4. **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`  
5. Add all env vars from section 12.  
6. Auto-deploy on push to `main`.

Free tier: first request can be slow (cold start). Keep the tab open while a job runs.

---

## 15. Example (invoice)

User uploads `hotel-bill.pdf`, type **Invoice**.

1. OCR text includes vendor, line items, tax, total.  
2. LLM fills `Invoice` JSON.  
3. Validation checks `subtotal + tax ≈ total`.  
4. If OK → category e.g. **Travel Expense** (keyword “hotel”) → row in Supabase `status=stored`.  
5. If totals mismatch → `needs_review`, nothing stored in `processed_documents`.

---

## 16. What was built (feature list)

- Pydantic models for Invoice, Receipt, KYC + date/ID validators  
- Mistral OCR agent (PDF + images)  
- LLM extraction with schema prompt + one repair retry  
- Rule-based validation + confidence  
- Keyword categorization  
- LangGraph orchestration + review branch  
- Supabase persist + error log  
- FastAPI + static UI  
- Async jobs so hosted HTTP does not time out  
- Gemini 503 retries / model fallback  

---

## 17. Limitations (honest)

- `doc_type_hint` is required for correct schema (no auto-detect yet).  
- Categorization is keywords, not LLM.  
- Job status lives **in memory**; a new Render deploy loses in-flight jobs.  
- `needs_review` does not write a processed snapshot (by design).  
- API keys must never be committed; rotate any key that was pasted in chat.  
- LLM/OCR outages (503, quota) still fail the job after retries.

---

## 18. Interview one-liner

> I built a LangGraph document pipeline: Mistral OCR, LLM JSON extraction against Pydantic schemas, rule validation with a review gate, then Supabase storage. FastAPI exposes an upload UI and job polling so other apps can integrate.
