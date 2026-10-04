"""Load dummy env before config.py. Works with unittest discover from tests/ or package imports."""

import os

_TEST_ENV = {
    "SUPABASE_URL": "https://docuflow-tests.example.invalid",
    "SUPABASE_KEY": "test-supabase-key",
    "OCR_API_KEY": "test-ocr-key",
    "OCR_ENDPOINT": "https://ocr.example.invalid/v1/ocr",
    "OCR_PROVIDER": "mistral",
    "LLM_API_KEY": "test-llm-key",
    "LLM_PROVIDER": "gemini",
    "SEARCH_API_KEY": "test-search-key",
    "MAX_UPLOAD_MB": "1",
    "UPLOAD_RATE_LIMIT": "10",
}

for _name, _value in _TEST_ENV.items():
    os.environ.setdefault(_name, _value)
