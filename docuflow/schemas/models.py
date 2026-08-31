import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    amount: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_amount(self) -> "InvoiceLineItem":
        expected = round(self.quantity * self.unit_price, 2)
        if abs(self.amount - expected) > 0.01:
            raise ValueError(
                f"amount ({self.amount}) must equal quantity * unit_price ({expected})"
            )
        return self


class Invoice(BaseModel):
    vendor_name: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    date: date
    line_items: list[InvoiceLineItem] = Field(min_length=1)
    subtotal: float = Field(ge=0)
    tax: float = Field(ge=0)
    total_amount: float = Field(ge=0)

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date:
        return _parse_date(value)

    @model_validator(mode="after")
    def validate_totals(self) -> "Invoice":
        line_sum = round(sum(item.amount for item in self.line_items), 2)
        if abs(self.subtotal - line_sum) > 0.01:
            raise ValueError(
                f"subtotal ({self.subtotal}) must equal sum of line item amounts ({line_sum})"
            )
        expected_total = round(self.subtotal + self.tax, 2)
        if abs(self.total_amount - expected_total) > 0.01:
            raise ValueError(
                f"total_amount ({self.total_amount}) must equal subtotal + tax ({expected_total})"
            )
        return self


class ReceiptItem(BaseModel):
    description: str
    amount: float = Field(ge=0)


class Receipt(BaseModel):
    merchant_name: str = Field(min_length=1)
    date: date
    items: list[ReceiptItem] = Field(min_length=1)
    total_amount: float = Field(ge=0)

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date:
        return _parse_date(value)

    @model_validator(mode="after")
    def validate_total(self) -> "Receipt":
        item_sum = round(sum(item.amount for item in self.items), 2)
        if abs(self.total_amount - item_sum) > 0.01:
            raise ValueError(
                f"total_amount ({self.total_amount}) must equal sum of item amounts ({item_sum})"
            )
        return self


class KYCDocumentType(str, Enum):
    AADHAAR = "Aadhaar"
    PAN = "PAN"
    PASSPORT = "Passport"


AADHAAR_PATTERN = re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PASSPORT_PATTERN = re.compile(r"^[A-Z][0-9]{7}$")


class KYCDocument(BaseModel):
    full_name: str = Field(min_length=1)
    document_type: KYCDocumentType
    id_number: str = Field(min_length=1)
    date_of_birth: date
    address: str = Field(min_length=1)

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, value: Any) -> date:
        return _parse_date(value)

    @field_validator("id_number", mode="before")
    @classmethod
    def normalize_id_number(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("id_number must be a string")
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_id_number_format(self) -> "KYCDocument":
        if self.document_type == KYCDocumentType.AADHAAR:
            normalized = re.sub(r"\s", "", self.id_number)
            if not re.fullmatch(r"\d{12}", normalized):
                raise ValueError(
                    "Aadhaar id_number must be 12 digits (optional spaces allowed)"
                )
            self.id_number = normalized
        elif self.document_type == KYCDocumentType.PAN:
            if not PAN_PATTERN.match(self.id_number):
                raise ValueError(
                    "PAN id_number must match format ABCDE1234F (5 letters, 4 digits, 1 letter)"
                )
        elif self.document_type == KYCDocumentType.PASSPORT:
            if not PASSPORT_PATTERN.match(self.id_number):
                raise ValueError(
                    "Passport id_number must match format A1234567 (1 letter followed by 7 digits)"
                )
        return self


class PipelineState(BaseModel):
    document_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    doc_type_hint: Optional[str] = None
    raw_text: Optional[str] = None
    extracted_data: Optional[dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    validation_errors: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    status: str = Field(min_length=1)


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ValueError(
                f"Unable to parse date: {value!r}. Expected ISO format or common date strings."
            ) from exc
    raise ValueError(f"Invalid date type: {type(value).__name__}")
