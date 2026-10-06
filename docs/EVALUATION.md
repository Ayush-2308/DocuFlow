# DocuFlow evaluation

Generated: 2026-10-06 02:32 UTC
Target: local uvicorn `http://127.0.0.1:8000` with real `.env` keys.
Samples: 4 dummy invoices, 3 dummy receipts, 3 dummy KYC PDFs in `docuflow/samples/`.
These numbers come from this run only. They are not estimates.

## OCR (Mistral, real PDF)

Probe `receipt_bookstore.pdf`: **FAIL in 4.70s** — HTTP 429 `rate_limited` code 1300. Follow-up PDF uploads on the same key also failed OCR, so field accuracy below is **Gemini extraction on the same dummy text as those PDFs**, not a successful Mistral pass.

## Gemini extraction + validation (dummy invoice / receipt / KYC text)

| File | Type | Expected | Actual | Match | Fields | Extract (s) | Total (s) | Note |
|---|---|---|---|---|---|---|---|---|
| `invoice_hotel.pdf` | invoice | stored | stored | True | 6/6 | 6.56 | 6.75 | |
| `invoice_office_supplies.pdf` | invoice | stored | stored | True | 6/6 | 18.63 | 18.70 | |
| `invoice_software.pdf` | invoice | stored | stored | True | 6/6 | 6.99 | 7.03 | |
| `invoice_total_mismatch.pdf` | invoice | needs_review | error | False | 0/6 | 25.72 | 25.72 | Gemini 429 quota |
| `receipt_coffee.pdf` | receipt | stored | stored | True | 3/3 | 15.76 | 15.87 | |
| `receipt_fuel.pdf` | receipt | stored | stored | True | 3/3 | 13.70 | 13.73 | |
| `receipt_bookstore.pdf` | receipt | stored | stored | True | 3/3 | 5.54 | 5.58 | |
| `kyc_aadhaar.pdf` | kyc | stored | stored | True | 5/5 | 7.78 | 7.84 | |
| `kyc_pan.pdf` | kyc | stored | stored | True | 5/5 | 9.18 | 9.30 | |
| `kyc_passport.pdf` | kyc | stored | error | False | 0/5 | 15.07 | 15.07 | Gemini 503 |

**Summary**

- Outcome accuracy: **8/10 (80.0%)**
- Field accuracy: **37/48 (77.1%)**
- Average Gemini extract: **12.49s**
- p95 Gemini extract: **25.72s**
- Average extract + validate (+ store when stored): **12.56s**
- p95 extract + validate (+ store when stored): **25.72s**

## HTTP upload of dummy PDFs

Health: HTTP 200 in **1.470s** — `llm_provider=gemini`, `gemini_model=gemini-3.6-flash`, `storage=sqlite`.

| File | HTTP | Upload (s) | Job (s) | E2E (s) | Job status | Error |
|---|---|---|---|---|---|---|
| `invoice_hotel.pdf` | 200 | 0.094 | 3.62 | 3.72 | error | Mistral OCR 429 |
| `invoice_office_supplies.pdf` | 200 | 0.045 | 6.56 | 6.60 | error | Mistral OCR 429 |
| `invoice_software.pdf` | 200 | 0.033 | 2.57 | 2.60 | error | Mistral OCR 429 |
| `invoice_total_mismatch.pdf` | 200 | 0.063 | 5.64 | 5.71 | error | Mistral OCR 429 |
| `receipt_coffee.pdf` | 200 | 0.099 | 8.80 | 8.90 | error | Mistral OCR 429 |
| `receipt_fuel.pdf` | 200 | 0.106 | 6.53 | 6.63 | error | Mistral OCR 429 |
| `receipt_bookstore.pdf` | 200 | 0.056 | 3.25 | 3.31 | error | Mistral OCR 429 |
| `kyc_aadhaar.pdf` | 200 | 0.019 | 3.10 | 3.12 | error | Mistral OCR 429 |
| `kyc_pan.pdf` | 200 | 0.071 | 6.77 | 6.84 | error | Mistral OCR 429 |
| `kyc_passport.pdf` | 200 | 0.045 | 4.77 | 4.82 | error | Mistral OCR 429 |

**Summary**

- Average upload HTTP: **0.063s**
- p95 upload HTTP: **0.106s**
- Average E2E (upload + failed OCR job): **5.23s**
- p95 E2E: **8.90s**
- All ten uploads returned HTTP 200; every job then failed at Mistral OCR 429.

## Search

Unauthenticated `GET /search`: HTTP **401** in **0.079s** (expected).

| Query | HTTP | Hits | Seconds |
|---|---|---|---|
| `SAMPLE USER ONE` | 200 | 1 | 0.056 |
| `SAMPLE Hotel Marriott` | 200 | 1 | 0.053 |
| `SAMPLE Starbucks` | 200 | 1 | 0.032 |
| `SAMPLE USER TWO` | 200 | 1 | 0.051 |

- Average authenticated search: **0.048s**
- p95 authenticated search: **0.056s**
