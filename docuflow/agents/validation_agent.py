import re
from datetime import date, datetime
from typing import Any

from schemas.models import PAN_PATTERN, PASSPORT_PATTERN, _parse_date

AMOUNT_TOLERANCE = 0.05

INVOICE_REQUIRED_FIELDS = (
    "vendor_name",
    "invoice_number",
    "date",
    "line_items",
    "subtotal",
    "tax",
    "total_amount",
)
RECEIPT_REQUIRED_FIELDS = ("merchant_name", "date", "items", "total_amount")
KYC_REQUIRED_FIELDS = (
    "full_name",
    "document_type",
    "id_number",
    "date_of_birth",
    "address",
)

AADHAAR_DIGITS = re.compile(r"^\d{12}$")


def validate(extracted_data: dict, doc_type: str) -> tuple[float, list[str]]:
    """Return a 0-1 confidence score and validation error messages."""
    data = extracted_data or {}
    kind = _normalize_doc_type(doc_type)
    errors: list[str] = []
    checks = 0

    required = _required_fields(kind)
    for field in required:
        checks += 1
        if _is_missing(data.get(field)):
            errors.append(f"Missing required field: {field}")

    date_fields = _date_fields(kind)
    today = date.today()
    for field in date_fields:
        if field not in data and field not in required:
            continue
        checks += 1
        parsed = _try_parse_date(data.get(field))
        if parsed is None:
            errors.append(f"{field} is not a valid date")
        elif parsed > today:
            errors.append(f"{field} is in the future ({parsed.isoformat()})")

    if kind == "invoice":
        checks += 1
        errors.extend(_validate_invoice_totals(data))

    if kind == "kyc":
        checks += 1
        id_error = _validate_id_number(data.get("id_number"), data.get("document_type"))
        if id_error:
            errors.append(id_error)

    checks = max(checks, 1)
    failed = min(len(errors), checks)
    confidence = round(max(0.0, 1.0 - (failed / checks)), 4)
    return confidence, errors


def _normalize_doc_type(doc_type: str) -> str:
    key = (doc_type or "").strip().lower().replace(" ", "_")
    if key in {"invoice"}:
        return "invoice"
    if key in {"receipt"}:
        return "receipt"
    if key in {"kyc", "kycdocument", "kyc_document"}:
        return "kyc"
    raise ValueError(
        f"Unsupported doc_type {doc_type!r}. Expected invoice, receipt, or kyc."
    )


def _required_fields(kind: str) -> tuple[str, ...]:
    if kind == "invoice":
        return INVOICE_REQUIRED_FIELDS
    if kind == "receipt":
        return RECEIPT_REQUIRED_FIELDS
    return KYC_REQUIRED_FIELDS


def _date_fields(kind: str) -> tuple[str, ...]:
    if kind == "kyc":
        return ("date_of_birth",)
    return ("date",)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _try_parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = _parse_date(value)
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, datetime):
        return parsed.date()
    return parsed


def _validate_invoice_totals(data: dict) -> list[str]:
    errors: list[str] = []
    line_items = data.get("line_items") or []
    if not isinstance(line_items, list) or not line_items:
        errors.append("Invoice line_items must be a non-empty list")
        return errors

    amounts: list[float] = []
    for index, item in enumerate(line_items):
        if not isinstance(item, dict):
            errors.append(f"line_items[{index}] must be an object")
            continue
        amount = _try_float(item.get("amount"))
        if amount is None:
            errors.append(f"line_items[{index}].amount is missing or not a number")
            continue
        amounts.append(amount)

        quantity = _try_float(item.get("quantity"))
        unit_price = _try_float(item.get("unit_price"))
        if quantity is not None and unit_price is not None:
            expected = round(quantity * unit_price, 2)
            if abs(amount - expected) > AMOUNT_TOLERANCE:
                errors.append(
                    f"line_items[{index}].amount ({amount}) does not equal "
                    f"quantity * unit_price ({expected})"
                )

    if not amounts:
        return errors

    line_sum = round(sum(amounts), 2)
    total = _try_float(data.get("total_amount"))
    subtotal = _try_float(data.get("subtotal"))
    tax = _try_float(data.get("tax"))

    if total is None:
        return errors

    if subtotal is not None and abs(line_sum - subtotal) > AMOUNT_TOLERANCE:
        errors.append(
            f"Line-item amounts ({line_sum}) do not sum to subtotal ({subtotal})"
        )

    if tax is not None and subtotal is not None:
        expected_total = round(subtotal + tax, 2)
        if abs(total - expected_total) > AMOUNT_TOLERANCE:
            errors.append(
                f"subtotal + tax ({expected_total}) does not equal total_amount ({total})"
            )
    elif abs(line_sum - total) > AMOUNT_TOLERANCE:
        if tax is not None and abs(round(line_sum + tax, 2) - total) <= AMOUNT_TOLERANCE:
            return errors
        errors.append(
            f"Line-item amounts ({line_sum}) do not sum to total_amount ({total}) "
            f"within tolerance {AMOUNT_TOLERANCE}"
        )

    return errors


def _validate_id_number(id_number: Any, document_type: Any) -> str | None:
    if _is_missing(id_number) or _is_missing(document_type):
        return None

    raw = str(id_number).strip().upper()
    doc = str(document_type).strip().lower()

    if doc == "aadhaar":
        digits = re.sub(r"\s", "", raw)
        if not AADHAAR_DIGITS.fullmatch(digits):
            return "id_number must be 12 digits for Aadhaar"
        return None
    if doc == "pan":
        if not PAN_PATTERN.fullmatch(raw):
            return "id_number must match PAN format ABCDE1234F"
        return None
    if doc == "passport":
        if not PASSPORT_PATTERN.fullmatch(raw):
            return "id_number must match Passport format A1234567"
        return None
    return f"Unknown document_type {document_type!r}; expected Aadhaar, PAN, or Passport"


def _try_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
