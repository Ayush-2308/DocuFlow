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
    pan = re.sub(r"\s", "", value).upper()
    if len(pan) < 5:
        return "XXXXX" + pan
    return "XXXXX" + pan[5:]


def sanitize_response(extracted_data: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of extracted_data with Aadhaar/PAN identifiers masked.

    Database rows are never modified; masking is response-layer only.
    """
    if not extracted_data:
        return {}
    data = copy.deepcopy(extracted_data)
    doc_type = str(data.get("document_type") or "").strip().lower()
    id_number = data.get("id_number")
    if isinstance(id_number, str) and id_number.strip():
        if doc_type == "aadhaar" or _looks_like_aadhaar(id_number):
            data["id_number"] = mask_aadhaar(id_number)
        elif doc_type == "pan" or _looks_like_pan(id_number):
            data["id_number"] = mask_pan(id_number)

    for key, value in list(data.items()):
        lowered = key.lower()
        if not isinstance(value, str):
            continue
        if "aadhaar" in lowered or "aadhar" in lowered:
            data[key] = mask_aadhaar(value)
        elif lowered == "pan" or lowered.endswith("_pan"):
            data[key] = mask_pan(value)
    return data


def _looks_like_aadhaar(value: str) -> bool:
    digits = _AADHAAR_DIGITS.sub("", value)
    return len(digits) == 12 and digits.isdigit()


def _looks_like_pan(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value.strip().upper()))
