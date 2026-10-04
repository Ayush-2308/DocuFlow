"""Generate synthetic SAMPLE PDFs under samples/. No real personal data."""

from __future__ import annotations

import json
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, lines: list[str]) -> None:
    body_lines = ["SAMPLE - NOT REAL", *lines]
    commands = ["BT", "/F1 12 Tf", "50 780 Td"]
    for index, line in enumerate(body_lines):
        leading = "16 TL T*" if index else ""
        prefix = f"{leading} " if leading else ""
        commands.append(f"{prefix}({_escape(line)}) Tj")
        if not index:
            commands.append("16 TL")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref_at = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(out))


def documents() -> list[dict]:
    return [
        {
            "file": "invoice_hotel.pdf",
            "doc_type": "invoice",
            "expected_outcome": "stored",
            "lines": [
                "INVOICE",
                "Vendor: SAMPLE Hotel Marriott Demo Pvt Ltd",
                "Invoice number: INV-SAMPLE-1001",
                "Date: 2024-03-15",
                "Line items:",
                "  Room night x 2 @ 4000.00 = 8000.00",
                "Subtotal: 8000.00",
                "Tax: 1440.00",
                "Total: 9440.00",
            ],
            "expected_fields": {
                "vendor_name": "SAMPLE Hotel Marriott Demo Pvt Ltd",
                "invoice_number": "INV-SAMPLE-1001",
                "date": "2024-03-15",
                "subtotal": 8000.00,
                "tax": 1440.00,
                "total_amount": 9440.00,
            },
        },
        {
            "file": "invoice_office_supplies.pdf",
            "doc_type": "invoice",
            "expected_outcome": "stored",
            "lines": [
                "INVOICE",
                "Vendor: SAMPLE Staples Office Depot Demo",
                "Invoice number: INV-SAMPLE-1002",
                "Date: 2024-04-02",
                "Line items:",
                "  Printer paper x 10 @ 50.00 = 500.00",
                "  Stapler x 1 @ 120.00 = 120.00",
                "Subtotal: 620.00",
                "Tax: 111.60",
                "Total: 731.60",
            ],
            "expected_fields": {
                "vendor_name": "SAMPLE Staples Office Depot Demo",
                "invoice_number": "INV-SAMPLE-1002",
                "date": "2024-04-02",
                "subtotal": 620.00,
                "tax": 111.60,
                "total_amount": 731.60,
            },
        },
        {
            "file": "invoice_software.pdf",
            "doc_type": "invoice",
            "expected_outcome": "stored",
            "lines": [
                "INVOICE",
                "Vendor: SAMPLE Adobe SaaS Subscription Demo",
                "Invoice number: INV-SAMPLE-1003",
                "Date: 2024-05-10",
                "Line items:",
                "  Creative Cloud seat x 1 @ 2000.00 = 2000.00",
                "Subtotal: 2000.00",
                "Tax: 360.00",
                "Total: 2360.00",
            ],
            "expected_fields": {
                "vendor_name": "SAMPLE Adobe SaaS Subscription Demo",
                "invoice_number": "INV-SAMPLE-1003",
                "date": "2024-05-10",
                "subtotal": 2000.00,
                "tax": 360.00,
                "total_amount": 2360.00,
            },
        },
        {
            "file": "invoice_total_mismatch.pdf",
            "doc_type": "invoice",
            "expected_outcome": "needs_review",
            "lines": [
                "INVOICE",
                "Vendor: SAMPLE Mismatch Cafe Demo",
                "Invoice number: INV-SAMPLE-1999",
                "Date: 2099-12-01",
                "Line items:",
                "  Demo meal x 1 @ 100.00 = 100.00",
                "Subtotal: 100.00",
                "Tax: 18.00",
                "Total: 999.00",
                "NOTE: printed total does not equal subtotal + tax (intentional SAMPLE error).",
            ],
            "expected_fields": {
                "vendor_name": "SAMPLE Mismatch Cafe Demo",
                "invoice_number": "INV-SAMPLE-1999",
                "date": "2099-12-01",
                "subtotal": 100.00,
                "tax": 18.00,
                "total_amount": 999.00,
            },
        },
        {
            "file": "receipt_coffee.pdf",
            "doc_type": "receipt",
            "expected_outcome": "stored",
            "lines": [
                "RECEIPT",
                "Merchant: SAMPLE Starbucks Cafe Demo",
                "Date: 2024-06-08",
                "Items:",
                "  Coffee 180.00",
                "  Sandwich 220.00",
                "Total: 400.00",
            ],
            "expected_fields": {
                "merchant_name": "SAMPLE Starbucks Cafe Demo",
                "date": "2024-06-08",
                "total_amount": 400.00,
            },
        },
        {
            "file": "receipt_fuel.pdf",
            "doc_type": "receipt",
            "expected_outcome": "stored",
            "lines": [
                "RECEIPT",
                "Merchant: SAMPLE Petrol Pump Demo",
                "Date: 2024-06-09",
                "Items:",
                "  Petrol 1500.00",
                "Total: 1500.00",
            ],
            "expected_fields": {
                "merchant_name": "SAMPLE Petrol Pump Demo",
                "date": "2024-06-09",
                "total_amount": 1500.00,
            },
        },
        {
            "file": "receipt_bookstore.pdf",
            "doc_type": "receipt",
            "expected_outcome": "stored",
            "lines": [
                "RECEIPT",
                "Merchant: SAMPLE Demo Bookstore",
                "Date: 2024-07-01",
                "Items:",
                "  Notebook 90.00",
                "  Pen 30.00",
                "Total: 120.00",
            ],
            "expected_fields": {
                "merchant_name": "SAMPLE Demo Bookstore",
                "date": "2024-07-01",
                "total_amount": 120.00,
            },
        },
        {
            "file": "kyc_aadhaar.pdf",
            "doc_type": "kyc",
            "expected_outcome": "stored",
            "lines": [
                "KYC DOCUMENT - AADHAAR (FAKE SAMPLE)",
                "Full name: SAMPLE USER ONE",
                "Document type: Aadhaar",
                "ID number: 999988887777",
                "Date of birth: 1990-01-01",
                "Address: 1 Sample Street, Demo Nagar, Test City 000001",
            ],
            "expected_fields": {
                "full_name": "SAMPLE USER ONE",
                "document_type": "Aadhaar",
                "id_number": "999988887777",
                "date_of_birth": "1990-01-01",
                "address": "1 Sample Street, Demo Nagar, Test City 000001",
            },
        },
        {
            "file": "kyc_pan.pdf",
            "doc_type": "kyc",
            "expected_outcome": "stored",
            "lines": [
                "KYC DOCUMENT - PAN (FAKE SAMPLE)",
                "Full name: SAMPLE USER TWO",
                "Document type: PAN",
                "ID number: AAAAA9999A",
                "Date of birth: 1991-02-02",
                "Address: 2 Sample Lane, Demo Pur, Test City 000002",
            ],
            "expected_fields": {
                "full_name": "SAMPLE USER TWO",
                "document_type": "PAN",
                "id_number": "AAAAA9999A",
                "date_of_birth": "1991-02-02",
                "address": "2 Sample Lane, Demo Pur, Test City 000002",
            },
        },
        {
            "file": "kyc_passport.pdf",
            "doc_type": "kyc",
            "expected_outcome": "stored",
            "lines": [
                "KYC DOCUMENT - PASSPORT (FAKE SAMPLE)",
                "Full name: SAMPLE USER THREE",
                "Document type: Passport",
                "ID number: Z9999999",
                "Date of birth: 1992-03-03",
                "Address: 3 Sample Road, Demo Bagh, Test City 000003",
            ],
            "expected_fields": {
                "full_name": "SAMPLE USER THREE",
                "document_type": "Passport",
                "id_number": "Z9999999",
                "date_of_birth": "1992-03-03",
                "address": "3 Sample Road, Demo Bagh, Test City 000003",
            },
        },
    ]


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    records = documents()
    truth = []
    for record in records:
        write_pdf(SAMPLES_DIR / record["file"], record["lines"])
        truth.append(
            {
                "file": record["file"],
                "doc_type": record["doc_type"],
                "expected_outcome": record["expected_outcome"],
                "expected_fields": record["expected_fields"],
            }
        )
    (SAMPLES_DIR / "ground_truth.json").write_text(
        json.dumps({"documents": truth}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} sample PDFs and ground_truth.json to {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
