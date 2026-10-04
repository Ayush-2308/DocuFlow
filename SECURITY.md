# Security

This file describes **what the code actually does**. It does not claim extra controls.

## Data

- KYC identifiers (Aadhaar, PAN, passport) that the model extracts are stored in full in `processed_documents`.
- Search responses mask Aadhaar and PAN only. Passport is not specially masked.
- The Upload result view is **not** masked.
- Temp files from `/upload` are deleted after the background job (`finally` in `_run_job`).

## Access

- `POST /upload` is unauthenticated. Limits: optional `MAX_UPLOAD_MB` (default 10 MB), PDF/PNG/JPEG only, per-IP `UPLOAD_RATE_LIMIT` (default 10/minute). That is abuse reduction, not login.
- `GET /search` and `DELETE /documents` require header `X-API-Key` equal to env `SEARCH_API_KEY`. That value is a shared secret, not per-user accounts.
- The Search tab Password field is that same secret. The browser may keep it in `sessionStorage` for the tab session.

## What this repo does not do

- No field-level encryption.
- No retention policy.
- No per-user authorization.
- In-memory rate limits do not apply across multiple Render instances.

## Next steps (not implemented)

Encryption at rest for identity fields, a retention/purge job, per-user auth, and masking on the upload result view.

Do not commit `.env` or real keys.
