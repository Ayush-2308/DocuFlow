import copy
import re
from typing import Any

_AADHAAR_DIGITS = re.compile(r"\D")


def mask_aadhaar(value: str) -> str:
    """Mask an Aadhaar number; only the last four digits remain visible."""
    digits = _AADHAAR_DIGITS.sub("", value)
    if len(digits) < 4:
        return "XXXX-XXXX-XXXX"
    return f"XXXX-XXXX-{digits[-4:]}"


def mask_pan(value: str) -> str:
    """Mask a PAN by replacing the first five characters with X."""
    pan = re.sub(r"[\s\-]", "", value).upper()
    if len(pan) < 5:
        return "XXXXX" + pan
    return "XXXXX" + pan[5:]


_AADHAAR_IN_TEXT = re.compile(r"(?<!\d)(?:\d[ \-]?){11}\d(?!\d)")
_PAN_IN_TEXT = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{5}[0-9]{4}[A-Za-z](?![A-Za-z0-9])")


def sanitize_response(
    extracted_data: dict[str, Any] | None,
    doc_hint: str | None = None,
) -> dict[str, Any]:
    """Return a copy of extracted_data with Aadhaar/PAN identifiers masked.

    Database rows are never modified; masking is response-layer only.
    """
    if not extracted_data:
        return {}
    data = copy.deepcopy(extracted_data)
    doc_type = str(data.get("document_type") or "").strip().lower()
    hint = str(doc_hint or "").strip().lower().replace(" ", "_")
    kyc = hint in {"kyc", "kycdocument", "kyc_document"} or _is_aadhaar_type(doc_type) or _is_pan_type(doc_type)

    id_text = _text_value(data.get("id_number"))
    if id_text:
        if _is_aadhaar_type(doc_type) or _looks_like_aadhaar(id_text):
            data["id_number"] = mask_aadhaar(id_text)
        elif _is_pan_type(doc_type) or _looks_like_pan(id_text):
            data["id_number"] = mask_pan(id_text)

    if kyc:
        for key, value in list(data.items()):
            if not isinstance(value, str) or key == "id_number":
                continue
            data[key] = mask_ids_in_text(value)
    else:
        for key, value in list(data.items()):
            lowered = key.lower()
            if not isinstance(value, str):
                continue
            if "aadhaar" in lowered or "aadhar" in lowered:
                data[key] = mask_aadhaar(value)
            elif lowered == "pan" or lowered.endswith("_pan"):
                data[key] = mask_pan(value)
    return data


def mask_ids_in_text(value: str) -> str:
    """Mask Aadhaar and PAN numbers embedded in a response string."""
    masked = _PAN_IN_TEXT.sub(lambda match: mask_pan(match.group(0)), value)
    return _AADHAAR_IN_TEXT.sub(lambda match: mask_aadhaar(match.group(0)), masked)


def _text_value(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str):
        return value.strip()
    return ""


def _is_aadhaar_type(doc_type: str) -> bool:
    return "aadhaar" in doc_type or "aadhar" in doc_type


def _is_pan_type(doc_type: str) -> bool:
    tokens = re.split(r"[\s_\-]+", doc_type)
    return "pan" in tokens


def _looks_like_aadhaar(value: str) -> bool:
    digits = _AADHAAR_DIGITS.sub("", value)
    return len(digits) == 12 and digits.isdigit()


def _looks_like_pan(value: str) -> bool:
    compact = re.sub(r"[\s\-]", "", value.strip().upper())
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", compact))
