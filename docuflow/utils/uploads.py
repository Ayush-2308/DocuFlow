from pathlib import Path

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

_PDF_MAGIC = b"%PDF"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8"


def sniff_kind(contents: bytes) -> str | None:
    if contents.startswith(_PDF_MAGIC):
        return "pdf"
    if contents.startswith(_PNG_MAGIC):
        return "png"
    if contents.startswith(_JPEG_MAGIC):
        return "jpeg"
    return None


def extension_kind(filename: str | None) -> str | None:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".png":
        return "png"
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    return None


def content_type_kind(content_type: str | None) -> str | None:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    if raw in {"application/pdf"}:
        return "pdf"
    if raw in {"image/png"}:
        return "png"
    if raw in {"image/jpeg", "image/jpg"}:
        return "jpeg"
    if raw in {"", "application/octet-stream"}:
        return None
    return "rejected"


def validate_upload_file(filename: str | None, content_type: str | None, contents: bytes) -> str | None:
    """Return an error message, or None if the file is an allowed PDF/PNG/JPEG."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return "Unsupported file type. Only PDF, PNG, and JPG/JPEG are allowed."

    sniffed = sniff_kind(contents)
    by_name = extension_kind(filename)
    by_type = content_type_kind(content_type)

    if by_type == "rejected":
        return "Unsupported content type. Only PDF, PNG, and JPG/JPEG are allowed."
    if sniffed is None:
        return "File contents do not look like a PDF, PNG, or JPEG."
    if by_name and sniffed != by_name:
        return "File extension does not match the file contents."
    if by_type and sniffed != by_type:
        return "Content type does not match the file contents."
    return None
