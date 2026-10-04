import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    ocr_api_key: str
    ocr_endpoint: str
    ocr_provider: str
    llm_api_key: str
    llm_provider: str
    search_api_key: str
    max_upload_mb: int
    upload_rate_per_minute: int


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _optional_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    token = str(raw).strip().split("/", 1)[0]
    try:
        value = int(token)
    except ValueError:
        return default
    return value if value > 0 else default


settings = Settings(
    supabase_url=_require_env("SUPABASE_URL"),
    supabase_key=_require_env("SUPABASE_KEY"),
    ocr_api_key=_require_env("OCR_API_KEY"),
    ocr_endpoint=_require_env("OCR_ENDPOINT"),
    ocr_provider=_require_env("OCR_PROVIDER"),
    llm_api_key=_require_env("LLM_API_KEY"),
    llm_provider=_require_env("LLM_PROVIDER"),
    search_api_key=_require_env("SEARCH_API_KEY"),
    max_upload_mb=_optional_positive_int("MAX_UPLOAD_MB", 10),
    upload_rate_per_minute=_optional_positive_int("UPLOAD_RATE_LIMIT", 10),
)
