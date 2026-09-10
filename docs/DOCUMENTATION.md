# DocuFlow — Full Documentation

This document matches the **current** codebase: what DocuFlow is, how each part works, the HTTP API, the Upload/Search UI, and how to run or deploy it.

| | |
|---|---|
| **Live UI** | https://docuflow-gbh3.onrender.com |
| **Source** | https://github.com/Ayush-2308/DocuFlow |
| **API docs (Swagger)** | `/docs` on the same host |
| **Default branch** | `main` |

---

## 1. What the project does

DocuFlow is a **multi-agent document automation pipeline**, exposed as a **web app + HTTP API**.

It is **not** a chatbot. Inside: specialized agents on a LangGraph. Outside: FastAPI plus a static UI with two tabs.

### Upload path

A user uploads a PDF or image (invoice, receipt, or KYC). The system:

1. Reads text from the file (**OCR** — Mistral).
2. Turns that text into structured JSON (**LLM extraction** — Gemini / OpenAI / Anthropic).
3. Checks required fields, dates, totals, and ID formats (**validation** — rules).
4. If quality is low, stops for **human review** (`needs_review`) and **does not** write a processed snapshot.
5. Otherwise assigns a **category** and **saves** the record in **Supabase**.

### Search path

A user (or another app) looks up **already stored** records by person or business name. Search does **not** re-run OCR. It queries `processed_documents` and returns JSON with Aadhaar/PAN **masked only in the response**. The Search tab is gated by a **Password** field that must equal env `SEARCH_API_KEY` (sent as `X-API-Key`). Upload stays public (no that header).

---

## 2. Problem it solves

Manually copying vendor names, invoice totals, or Aadhaar/PAN fields from PDFs is slow and error-prone. DocuFlow automates:

ingest → extract → validate → route → store  

Other apps can `POST /upload`, poll `GET /jobs/{job_id}`, call `GET /search`, or read Supabase instead of parsing PDFs themselves.

---

## 3. Tech stack

| Layer | Choice |
|--------|--------|
| Language | Python 3.12+ (Render may pin `3.12.10` via `render.yaml`) |
| API / UI host | FastAPI + Uvicorn |
| Orchestration | LangGraph `StateGraph` |
| Schemas | Pydantic v2 |
| OCR | Mistral OCR HTTP API |
| Extraction LLM | Configurable: `gemini`, `openai`, `anthropic` |
| Gemini model | **`gemini-3.6-flash` only** (older `gemini-2.5-flash` 404s for new keys) |
| Database | Supabase (Postgres + JSONB) |
| Frontend | Static HTML / CSS / JS (no React build) |
| Config | `python-dotenv` + required environment variables |
| HTTP clients | `httpx` |
| Tests | `unittest` for response masking (`docuflow/tests/test_sanitize.py`) |

---

## 4. Repository layout

```
DocuFlow/
├── README.md                 # Short GitHub overview
├── docs/DOCUMENTATION.md     # This file
├── render.yaml               # Render: rootDir docuflow, pip + uvicorn
├── .gitignore                # Ignores .env, venv, caches
└── docuflow/                 # Application root (run uvicorn from here)
    ├── main.py               # FastAPI: UI, jobs, search auth
    ├── graph.py              # LangGraph pipeline
    ├── config.py             # Loads required env vars (fails if any missing)
    ├── requirements.txt
    ├── Procfile              # web: uvicorn main:app --host 0.0.0.0 --port $PORT
    ├── .env.example          # Placeholder keys (commit this, never .env)
    ├── schemas/
    │   └── models.py         # Invoice, Receipt, KYC, PipelineState
    ├── agents/
    │   ├── ocr_agent.py
    │   ├── extraction_agent.py
    │   ├── validation_agent.py
    │   ├── categorization_agent.py
    │   └── search_agent.py   # NL intent + identity lookup
    ├── db/
    │   ├── supabase_client.py
    │   └── migrations.sql
    ├── utils/
    │   └── sanitize.py       # Aadhaar/PAN mask on search responses
    ├── tests/
    │   └── test_sanitize.py
    └── static/
        ├── index.html        # Upload | Search tabs
        ├── styles.css
        └── app.js
```

**Secrets:** `docuflow/.env` is gitignored. Only `.env.example` is on GitHub. Never commit real keys.

---

## 5. End-to-end flows

### 5.1 Upload (browser or API)

```
Browser UI (Upload tab)
  POST /upload (multipart: file + doc_type_hint)
        │
        ├─ save temp file
        ├─ return { job_id, status: "processing" }   ◄── HTTP ends quickly
        │
        └─ background task: run_pipeline()
                  │
   LangGraph: intake → ocr → extraction → validation
                  │
                  score < 0.75 or errors? ────┤
                  yes → needs_review → END    │
                  no  → categorize → storage (Supabase) → END
                  │
Browser polls GET /jobs/{job_id} every 2s (up to 5 minutes)
                  │
UI shows status, category, confidence, extracted fields
```

**Why background jobs?** Hosts like Render close long HTTP requests (~30–100s). OCR + LLM often take longer. Upload returns immediately; the client polls until `done` or `error`.

Jobs are stored **in process memory**. A Render restart or new deploy drops in-flight `job_id`s.

### 5.2 Search (browser or API)

```
Browser UI (Search tab)
  query text + Password
        │
  GET /search?query=...
  Header: X-API-Key: <same value as SEARCH_API_KEY>
        │
  401 if missing/wrong key
        │
  parse_search_intent (plain name skips LLM; phrases use LLM)
        │
  search_processed_documents (ILIKE on JSONB name fields)
        │
  sanitize_response (Aadhaar/PAN masked; DB unchanged)
        │
  JSON { query, results: [{ document_type, document_id, data }] }
```

---

## 6. Pipeline state (`PipelineState`)

Shared state for every graph node (`schemas/models.py`):

| Field | Meaning |
|--------|---------|
| `document_id` | UUID for this run |
| `file_path` | Temp path of the uploaded file (deleted after the job) |
| `doc_type_hint` | `invoice` / `receipt` / `kyc` |
| `raw_text` | OCR output |
| `extracted_data` | Validated JSON dict |
| `confidence_score` | 0–1 from validation |
| `validation_errors` | List of rule failures |
| `category` | e.g. Travel Expense, Identity Verification |
| `status` | `pending` → `intake` → `ocr` → `extracted` → `validated` → `categorized` / `needs_review` / `stored` |

### 6.1 Document schemas

**Invoice:** `vendor_name`, `invoice_number`, `date`, `line_items[]` (`description`, `quantity`, `unit_price`, `amount`), `subtotal`, `tax`, `total_amount`. Line amount must equal `quantity * unit_price`; subtotal must equal line sum; total must equal subtotal + tax (0.01 tolerance in Pydantic; validation agent uses 0.05 on totals).

**Receipt:** `merchant_name`, `date`, `items[]` (`description`, `amount`), `total_amount` equal to item sum.

**KYC:** `full_name`, `document_type` (`Aadhaar` / `PAN` / `Passport`), `id_number`, `date_of_birth`, `address`.

- Aadhaar: 12 digits (spaces allowed on input, stored normalized).
- PAN: `ABCDE1234F` (5 letters, 4 digits, 1 letter).
- Passport: `A1234567` (1 letter + 7 digits).

Dates accept ISO and common `DD/MM/YYYY`-style strings.

---

## 7. Agents

### 7.1 OCR (`agents/ocr_agent.py`)

- **Input:** local file path  
- **Output:** extracted text (page markdown joined)  
- **How:** Base64 data URL to Mistral `POST {OCR_ENDPOINT}` (`https://api.mistral.ai/v1/ocr`)  
- PDFs → `document_url` + `application/pdf`  
- Images → `image_url` + MIME from extension (png, jpg, webp, …)  
- Failures raise `OCRError` (missing file, HTTP error, empty text)

### 7.2 Extraction (`agents/extraction_agent.py`)

- **Input:** `raw_text`, `doc_type_hint`  
- **Output:** dict matching `Invoice`, `Receipt`, or `KYCDocument`  
- **How:** Prompt includes the Pydantic JSON schema; model must return JSON only  
- Parses JSON (strips markdown fences); `model_validate`  
- If invalid, **one correction prompt** with the error, then retry  
- **Providers** (`LLM_PROVIDER`):
  - `openai` — Chat Completions (`gpt-4o-mini`)
  - `anthropic` — Messages API (`claude-3-5-sonnet-latest`)
  - `gemini` / `google` — `generateContent` on **`gemini-3.6-flash`**; retries on 429/503

### 7.3 Validation (`agents/validation_agent.py`)

- **Input:** extracted dict + doc type  
- **Output:** `(confidence_score, error_list)`  
- **Rules:**
  - Required fields present  
  - Dates parse and are not in the future  
  - Invoices: line amounts vs subtotal / tax / total (tolerance `0.05`)  
  - KYC `id_number`: Aadhaar 12 digits, PAN pattern, Passport pattern  
- Confidence ≈ `1 - failed_checks / total_checks`

### 7.4 Categorization (`agents/categorization_agent.py`)

- Keyword match on vendor/merchant name and item descriptions  
- KYC always → `Identity Verification`  
- Else Travel Expense, Office Supplies, Meals & Entertainment, Software, or `Uncategorized`  
- Code still has a TODO to replace this with an LLM later  

### 7.5 Search (`agents/search_agent.py`)

Not part of the LangGraph upload pipeline. Used only by `GET /search`.

- **`parse_search_intent`:** a short name (≤ 4 words, no cues like “show”, “last”, “invoice”) is used as-is. Longer / NL phrases call the same LLM helper as extraction and expect `{name, doc_type, latest}`. LLM failure → treat the full string as `name`.
- **`search_identity`:** queries Supabase, optionally keeps only the newest row if `latest` is true, sorts results KYC → invoice → receipt, applies `sanitize_response`.

### 7.6 Storage (`db/supabase_client.py`)

- `insert_document` — upsert `documents`, insert `processed_documents`  
- `update_document_status` — set `documents.status`  
- `log_pipeline_error` — append to `pipeline_errors`  
- `search_processed_documents` — ILIKE on `extracted_data->>full_name`, `vendor_name`, `merchant_name`; optional `doc_type_hint` filter; `%` `_` and similar stripped from the needle  
- `delete_documents` — looks up ids, deletes matching `pipeline_errors` and `documents` (`processed_documents` cascade) 

Called from the **storage** graph node. Job exceptions also try `log_pipeline_error`.

---

## 8. LangGraph (`graph.py`)

Nodes:

`intake` → `ocr` → `extraction` → `validation` → **branch**

- If `validation_errors` is non-empty **or** `confidence_score < 0.75` (or score is `None`) → `needs_review` → END (no category, no Supabase processed insert).  
- Else → `categorization` → `storage` → END  

`run_pipeline(file_path, doc_type_hint, document_id=None)` builds initial `PipelineState` and `invoke`s the compiled graph.

---

## 9. HTTP API (`main.py`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/` | none | Static UI (`index.html`) |
| `GET` | `/static/*` | none | CSS / JS |
| `GET` | `/health` | none | `{ ok, llm_provider, gemini_model }` |
| `GET` | `/docs` | none | Swagger |
| `POST` | `/upload` | none | Multipart `file` + `doc_type_hint` → `{ job_id, status: "processing" }` |
| `GET` | `/jobs/{job_id}` | none | `processing` / `{ status: done, result }` / `{ status: error, error }` |
| `GET` | `/search?query=` | **`X-API-Key`** | Identity search over stored `extracted_data` |
| `DELETE` | `/documents` | **`X-API-Key`** | Body `{ "document_ids": ["uuid", ...] }` (1–50 UUIDs) → `{ deleted, count }` |

`doc_type_hint` values: `invoice`, `receipt`, `kyc` (agents treat related aliases as KYC). Empty upload body → **400**.

### 9.1 Identity search details

`GET /search?query={text}` looks up **stored** rows only.

**Auth:** header `X-API-Key` must equal env `SEARCH_API_KEY`. Missing or wrong → **401** `Invalid or missing API key`. Empty query → **400**. Downstream errors → **500**.

**Masking:** `utils/sanitize.py` → `sanitize_response()`. **Response only**; database rows stay full.

- Aadhaar `id_number`: `XXXX-XXXX-` + last 4 digits  
- PAN `id_number`: first 5 characters → `X` (e.g. `ABCDE1234F` → `XXXXX1234F`)  
- Also masks string fields whose keys look like Aadhaar/PAN  

Passport numbers are **not** specially masked.

**Example**

```http
GET /search?query=Ayush
X-API-Key: <SEARCH_API_KEY>
```

```json
{
  "query": "Ayush",
  "results": [
    {
      "document_type": "kyc",
      "document_id": "...",
      "data": { "full_name": "...", "id_number": "XXXX-XXXX-0123" }
    },
    {
      "document_type": "invoice",
      "document_id": "...",
      "data": { "vendor_name": "..." }
    }
  ]
}
```

**Delete selected records** (same `X-API-Key` as search):

```http
DELETE /documents
X-API-Key: <SEARCH_API_KEY>
Content-Type: application/json

{ "document_ids": ["<uuid>"] }
```

**curl upload then poll**

```bash
curl -X POST "http://127.0.0.1:8000/upload" \
  -F "file=@./sample-invoice.pdf" \
  -F "doc_type_hint=invoice"

curl "http://127.0.0.1:8000/jobs/<job_id>"
```

---

## 10. Database (`db/migrations.sql`)

Run once in the Supabase SQL editor.

| Table | Role |
|--------|------|
| `documents` | `document_id` PK, path, type hint, status, timestamps |
| `processed_documents` | Full snapshot including JSONB `extracted_data`, confidence, errors, category |
| `pipeline_errors` | Error strings per `document_id` |

Indexes on `processed_documents.document_id` and `pipeline_errors.document_id`.

Search needs `extracted_data` JSON keys `full_name`, `vendor_name`, and/or `merchant_name` depending on document type.

---

## 11. Frontend (`static/`)

Two tabs: **Upload** and **Search**. Paper/cream layout (Fraunces + Source Sans 3).

### Upload

- Drag-and-drop or file picker (PDF, PNG, JPG)  
- Document type dropdown (required)  
- `POST /upload` then poll `/jobs/{id}` every 2 seconds, timeout 5 minutes  
- Chips: status, category, confidence; extracted fields; validation errors; collapsible OCR text and full JSON  

**Note:** the upload result panel shows extraction JSON as returned by the job. Masking is applied on **search** responses, not on this upload result view.

### Search

- **Search** — name or a phrase like `show me Ayush's last invoice`  
- **Password** — must be the server’s `SEARCH_API_KEY` (not a user account password). The UI label is “Password” so the page does not advertise “API key”. The value is **not** prefilled; without it, search returns 401.  
- Browser stores the last typed password in `sessionStorage` (`docuflowSearchKey`) for that tab session only  
- `GET /search?query=...` with header `X-API-Key`  
- Renders each hit as type + `document_id` + field list  
- **Select all** / per-row checkboxes + **Delete selected** (confirm, then `DELETE /documents` with the same password; list refreshes) 

---

## 12. Environment variables

Copy `docuflow/.env.example` → `docuflow/.env` locally. On Render, set the **same names** under Environment.

| Variable | Role |
|----------|------|
| `SUPABASE_URL` | Project URL `https://….supabase.co` |
| `SUPABASE_KEY` | Server key (`sb_secret_…` or service_role JWT) |
| `OCR_API_KEY` | Mistral API key |
| `OCR_ENDPOINT` | `https://api.mistral.ai/v1/ocr` |
| `OCR_PROVIDER` | `mistral` |
| `LLM_API_KEY` | Gemini / OpenAI / Anthropic key |
| `LLM_PROVIDER` | `gemini` \| `openai` \| `anthropic` |
| `SEARCH_API_KEY` | Shared secret for `GET /search` and the UI Password field |

`config.py` **raises at import** if any are missing. A hosted app with incomplete env will crash on boot (`Missing required environment variable: …`).

Pick a long random `SEARCH_API_KEY`. Do not commit it. Rotate any key that was pasted in chat or screenshots.

---

## 13. Local setup

```bash
cd docuflow
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # then fill real keys
```

1. Run `db/migrations.sql` in the Supabase SQL editor.  
2. Start the app from **`docuflow/`**:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

3. UI: http://127.0.0.1:8000  
4. Swagger: http://127.0.0.1:8000/docs  

Sanitize tests (from `docuflow/`):

```bash
python -m unittest tests.test_sanitize
```

---

## 14. Deploy (Render)

1. Connect GitHub `Ayush-2308/DocuFlow`.  
2. **Root Directory:** `docuflow`  
3. **Build:** `pip install -r requirements.txt`  
4. **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`  
5. Set **all** variables in section 12, including `SEARCH_API_KEY`.  
6. Auto-deploy on push to `main`.

Free tier: first request can be slow (cold start). Keep the tab open while an upload job runs.

---

## 15. Worked examples

### Invoice

User uploads `hotel-bill.pdf`, type **Invoice**.

1. OCR text includes vendor, line items, tax, total.  
2. LLM fills `Invoice` JSON.  
3. Validation checks `subtotal + tax ≈ total`.  
4. If OK → category e.g. **Travel Expense** (keyword “hotel”) → `processed_documents` with `status=stored`.  
5. If totals mismatch → `needs_review`; nothing stored in `processed_documents`.

### KYC then search

1. Upload Aadhaar image, type **KYC**, wait until status `stored`.  
2. Search tab: query `full_name` (or a short name), Password = `SEARCH_API_KEY`.  
3. Response `id_number` looks like `XXXX-XXXX-0123`. The row in Supabase still has the full number.

---

## 16. Feature list (what is built)

- Pydantic models for Invoice, Receipt, KYC + date/ID validators  
- Mistral OCR agent (PDF + images)  
- LLM extraction with schema prompt + one repair retry  
- Rule-based validation + confidence  
- Keyword categorization  
- LangGraph orchestration + review branch  
- Supabase persist + error log  
- FastAPI + static UI with **Upload** and **Search** tabs  
- Async jobs so hosted HTTP does not time out  
- Gemini 429/503 retries; extraction model **`gemini-3.6-flash` only**  
- Identity search (`GET /search`) with NL intent, ILIKE name match, Aadhaar/PAN response masking, `X-API-Key`  
- Select-and-delete stored documents (`DELETE /documents`) from the Search tab  
- UI Password field (not prefilled) mapped to that header  

---

## 17. Limitations (honest)

- `doc_type_hint` is required for the correct schema (no auto-detect).  
- Categorization is keywords, not LLM.  
- Job status lives **in memory**; deploys lose in-flight jobs.  
- `needs_review` does not write a processed snapshot (by design), so those docs are **not** searchable.  
- Upload result UI can still show full `id_number`; masking is search-response only.  
- Search Password in the browser is a shared env secret, not per-user auth. Anyone who knows it can query stored names.  
- Gemini/OCR outages or quota still fail the job after retries.  
- API keys must never be committed.

---

## 18. Interview one-liner

> I built a LangGraph document pipeline: Mistral OCR, LLM JSON extraction against Pydantic schemas, rule validation with a review gate, then Supabase storage. FastAPI exposes an upload UI with job polling plus a password-gated identity search that masks Aadhaar and PAN on the way out so other apps can integrate without parsing PDFs themselves.
