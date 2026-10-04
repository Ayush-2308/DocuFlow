# Changelog

Entries are taken from `git log` on `main`. Dates are commit dates.

## Unreleased

- Enforce upload size, type, and per-IP rate limits.
- Add synthetic SAMPLE documents and a generator script.
- Add evaluation script and placeholder EVALUATION.md.
- Add unittest coverage for pipeline rules and upload API.
- Document architecture, retries, security, and troubleshooting.
- Add LICENSE and repo hygiene.

## 2026-09-19

- Fall back to SQLite when Supabase hostname cannot be resolved.

## 2026-09-10

- Bust cached Search JS so the delete checkboxes show on Render.
- Add Search-tab document selection and delete, and refresh docs.

## 2026-09-03

- Rename search key field to Password and stop prefilling it.
- Prefill Search API key field with the default SEARCH_API_KEY value.
- Add Upload and Search tabs to the web UI.
- Use only gemini-3.6-flash after 2.5-flash was retired for new keys.
- Merge remote main and keep project documentation.
- Add identity search with response masking and API key auth.

## 2026-09-02

- Delete docs/DOCUMENTATION.md
- Add full project documentation and refresh the GitHub README.
- Run the pipeline in the background so Render does not time out uploads.
- Retry Gemini 503s and fall back to other Flash models.
- Merge branch `main` of https://github.com/Ayush-2308/DocuFlow
- Add document pipeline, FastAPI upload UI, and Supabase storage.

## 2026-08-31

- Merge pull request #1 from Ayush-2308/ayush/mistral-ocr-agent
- Add Mistral OCR agent for PDF and image extraction.
- docuflow/README.md
- Initial commit: DocuFlow document processing scaffold
