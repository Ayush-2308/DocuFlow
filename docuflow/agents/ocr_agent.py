import base64
from pathlib import Path

import httpx

from config import settings

OCR_MODEL = "mistral-ocr-latest"

IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


class OCRError(Exception):
    """Raised when OCR fails or returns no extractable text."""


def run_ocr(file_path: str) -> str:
    """Send a local PDF or image to the Mistral OCR API and return extracted text."""
    path = Path(file_path)
    if not path.is_file():
        raise OCRError(f"File not found: {file_path}")

    content_type, document = _build_document_payload(path)
    payload = {"model": OCR_MODEL, "document": document}

    try:
        response = httpx.post(
            settings.ocr_endpoint,
            headers={
                "Authorization": f"Bearer {settings.ocr_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        raise OCRError(
            f"Mistral OCR request failed with status {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OCRError(f"Mistral OCR request failed: {exc}") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise OCRError("Mistral OCR returned a non-JSON response") from exc

    text = _extract_text(body)
    if not text:
        raise OCRError(
            f"Mistral OCR returned empty text for {path.name} ({content_type})"
        )
    return text


def _build_document_payload(path: Path) -> tuple[str, dict]:
    suffix = path.suffix.lower()
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")

    if suffix == ".pdf":
        content_type = "application/pdf"
        data_url = f"data:{content_type};base64,{encoded}"
        return content_type, {"type": "document_url", "document_url": data_url}

    content_type = IMAGE_CONTENT_TYPES.get(suffix)
    if content_type is None:
        raise OCRError(
            f"Unsupported file type {suffix or '(none)'}. "
            "Expected a PDF or image (.png, .jpg, .jpeg, .webp, .gif, .bmp, .tiff)."
        )

    data_url = f"data:{content_type};base64,{encoded}"
    return content_type, {"type": "image_url", "image_url": data_url}


def _extract_text(body: dict) -> str:
    pages = body.get("pages") or []
    page_text = "\n\n".join(
        (page.get("markdown") or page.get("text") or "").strip()
        for page in pages
        if isinstance(page, dict)
    ).strip()
    if page_text:
        return page_text

    fallback = body.get("text") or body.get("markdown") or ""
    return fallback.strip() if isinstance(fallback, str) else ""
