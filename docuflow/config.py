import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    ocr_api_key: str
    llm_api_key: str
    llm_provider: str


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


settings = Settings(
    supabase_url=_require_env("SUPABASE_URL"),
    supabase_key=_require_env("SUPABASE_KEY"),
    ocr_api_key=_require_env("OCR_API_KEY"),
    llm_api_key=_require_env("LLM_API_KEY"),
    llm_provider=_require_env("LLM_PROVIDER"),
)
