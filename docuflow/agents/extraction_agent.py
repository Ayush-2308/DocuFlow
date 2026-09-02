import json
import re
from typing import Any, Type

import httpx
from pydantic import BaseModel, ValidationError

from config import settings
from schemas.models import Invoice, KYCDocument, Receipt

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_GENERATE_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODEL = "claude-3-5-sonnet-latest"
ANTHROPIC_VERSION = "2023-06-01"

DOC_TYPE_MODELS: dict[str, Type[BaseModel]] = {
    "invoice": Invoice,
    "receipt": Receipt,
    "kyc": KYCDocument,
    "kycdocument": KYCDocument,
    "kyc_document": KYCDocument,
}

EXTRACTION_PROMPT_TEMPLATE = """You are a document data extractor.

Extract fields from the document text and return ONLY valid JSON that matches this schema.
Do not include markdown, comments, or any text outside the JSON object.
Use ISO dates (YYYY-MM-DD). Infer missing numeric totals from line items when possible.
If a required value is truly absent, use a best-effort empty-but-typed placeholder only when the schema allows it; otherwise omit nothing required — use empty string or 0 only if that is honest to the source.

Document type: {schema_name}

JSON schema:
{schema_json}

Document text:
{raw_text}
"""

CORRECTION_PROMPT_TEMPLATE = """You are a document data extractor.

Your previous JSON did not validate. Return ONLY corrected valid JSON that matches the schema.
Do not include markdown, comments, or any text outside the JSON object.
Use ISO dates (YYYY-MM-DD). Fix the validation error while staying faithful to the document text.

Document type: {schema_name}

JSON schema:
{schema_json}

Validation error:
{error_message}

Previous JSON:
{previous_json}

Document text:
{raw_text}
"""


class ExtractionError(Exception):
    """Raised when field extraction or schema validation fails."""


def build_extraction_prompt(raw_text: str, schema_name: str, schema_json: str) -> str:
    return _fill_template(
        EXTRACTION_PROMPT_TEMPLATE,
        schema_name=schema_name,
        schema_json=schema_json,
        raw_text=raw_text,
    )


def build_correction_prompt(
    raw_text: str,
    schema_name: str,
    schema_json: str,
    error_message: str,
    previous_json: str,
) -> str:
    return _fill_template(
        CORRECTION_PROMPT_TEMPLATE,
        schema_name=schema_name,
        schema_json=schema_json,
        error_message=error_message,
        previous_json=previous_json,
        raw_text=raw_text,
    )


def extract_fields(raw_text: str, doc_type_hint: str) -> dict:
    """Call the configured LLM and return JSON validated against the hinted Pydantic schema."""
    if not raw_text or not raw_text.strip():
        raise ExtractionError("raw_text is empty; nothing to extract")

    model_cls = _resolve_model(doc_type_hint)
    schema_name = model_cls.__name__
    schema_json = json.dumps(model_cls.model_json_schema(), indent=2)

    prompt = build_extraction_prompt(raw_text.strip(), schema_name, schema_json)
    llm_text = _call_llm(prompt)
    parsed, parse_error = _parse_json_object(llm_text)

    if parsed is not None:
        validated, validation_error = _validate_payload(model_cls, parsed)
        if validated is not None:
            return validated
        error_message = validation_error or "Unknown validation error"
        previous_json = json.dumps(parsed, default=str)
    else:
        error_message = parse_error or "LLM response was not valid JSON"
        previous_json = llm_text.strip()

    correction_prompt = build_correction_prompt(
        raw_text=raw_text.strip(),
        schema_name=schema_name,
        schema_json=schema_json,
        error_message=error_message,
        previous_json=previous_json,
    )
    retry_text = _call_llm(correction_prompt)
    retry_parsed, retry_parse_error = _parse_json_object(retry_text)
    if retry_parsed is None:
        raise ExtractionError(
            f"LLM JSON parsing failed after retry: {retry_parse_error}"
        )

    retry_validated, retry_validation_error = _validate_payload(model_cls, retry_parsed)
    if retry_validated is None:
        raise ExtractionError(
            f"Extracted JSON did not match {schema_name} after retry: {retry_validation_error}"
        )
    return retry_validated


def _resolve_model(doc_type_hint: str) -> Type[BaseModel]:
    key = (doc_type_hint or "").strip().lower().replace(" ", "_")
    model_cls = DOC_TYPE_MODELS.get(key)
    if model_cls is None:
        supported = ", ".join(sorted(set(DOC_TYPE_MODELS)))
        raise ExtractionError(
            f"Unsupported doc_type_hint {doc_type_hint!r}. Expected one of: {supported}"
        )
    return model_cls


def _validate_payload(
    model_cls: Type[BaseModel], payload: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        instance = model_cls.model_validate(payload)
        return instance.model_dump(mode="json"), None
    except ValidationError as exc:
        return None, str(exc)


def _parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"

    if not isinstance(value, dict):
        return None, f"Expected a JSON object, got {type(value).__name__}"
    return value, None


def _call_llm(prompt: str) -> str:
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        return _call_openai(prompt)
    if provider == "anthropic":
        return _call_anthropic(prompt)
    if provider in {"gemini", "google", "google_gemini"}:
        return _call_gemini(prompt)
    raise ExtractionError(
        f"Unsupported LLM_PROVIDER {settings.llm_provider!r}. "
        "Expected 'openai', 'anthropic', or 'gemini'."
    )


def _call_openai(prompt: str) -> str:
    try:
        response = httpx.post(
            OPENAI_CHAT_URL,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "Return only valid JSON. No markdown or extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise ExtractionError(
            f"OpenAI request failed with status {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ExtractionError(f"OpenAI request failed: {exc}") from exc

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ExtractionError("OpenAI returned an unexpected response shape") from exc

    if not content or not str(content).strip():
        raise ExtractionError("OpenAI returned an empty response")
    return str(content)


def _call_anthropic(prompt: str) -> str:
    try:
        response = httpx.post(
            ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": settings.llm_api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4096,
                "temperature": 0,
                "system": "Return only valid JSON. No markdown or extra text.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise ExtractionError(
            f"Anthropic request failed with status {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ExtractionError(f"Anthropic request failed: {exc}") from exc

    try:
        body = response.json()
        blocks = body.get("content") or []
        text_parts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        content = "".join(text_parts).strip()
    except (ValueError, TypeError) as exc:
        raise ExtractionError("Anthropic returned an unexpected response shape") from exc

    if not content:
        raise ExtractionError("Anthropic returned an empty response")
    return content


def _call_gemini(prompt: str) -> str:
    try:
        response = httpx.post(
            GEMINI_GENERATE_URL,
            headers={
                "x-goog-api-key": settings.llm_api_key,
                "Content-Type": "application/json",
            },
            json={
                "systemInstruction": {
                    "parts": [
                        {"text": "Return only valid JSON. No markdown or extra text."}
                    ]
                },
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise ExtractionError(
            f"Gemini request failed with status {exc.response.status_code} "
            f"(model={GEMINI_MODEL}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ExtractionError(f"Gemini request failed: {exc}") from exc

    try:
        body = response.json()
        parts = body["candidates"][0]["content"]["parts"]
        content = "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        ).strip()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ExtractionError("Gemini returned an unexpected response shape") from exc

    if not content:
        raise ExtractionError("Gemini returned an empty response")
    return content


def _fill_template(template: str, **values: str) -> str:
    filled = template
    for key, value in values.items():
        filled = filled.replace("{" + key + "}", value)
    return filled
