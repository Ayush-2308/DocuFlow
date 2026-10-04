import unittest
from datetime import date

from pydantic import ValidationError

from schemas.models import Invoice, KYCDocument, Receipt


class SchemaTests(unittest.TestCase):
    def test_invoice_accepts_iso_and_slash_dates(self) -> None:
        payload = {
            "vendor_name": "SAMPLE Vendor",
            "invoice_number": "INV-1",
            "date": "15/03/2024",
            "line_items": [
                {
                    "description": "Item",
                    "quantity": 2,
                    "unit_price": 10,
                    "amount": 20,
                }
            ],
            "subtotal": 20,
            "tax": 2,
            "total_amount": 22,
        }
        invoice = Invoice.model_validate(payload)
        self.assertEqual(invoice.date, date(2024, 3, 15))

        payload["date"] = "2024-03-15"
        self.assertEqual(Invoice.model_validate(payload).date, date(2024, 3, 15))

    def test_invoice_rejects_amount_mismatch(self) -> None:
        payload = {
            "vendor_name": "SAMPLE Vendor",
            "invoice_number": "INV-1",
            "date": "2024-03-15",
            "line_items": [
                {
                    "description": "Item",
                    "quantity": 1,
                    "unit_price": 10,
                    "amount": 99,
                }
            ],
            "subtotal": 99,
            "tax": 0,
            "total_amount": 99,
        }
        with self.assertRaises(ValidationError):
            Invoice.model_validate(payload)

    def test_receipt_total_must_match_items(self) -> None:
        good = {
            "merchant_name": "SAMPLE Shop",
            "date": "2024-01-01",
            "items": [{"description": "A", "amount": 10}, {"description": "B", "amount": 5}],
            "total_amount": 15,
        }
        self.assertEqual(Receipt.model_validate(good).total_amount, 15)
        good["total_amount"] = 20
        with self.assertRaises(ValidationError):
            Receipt.model_validate(good)

    def test_kyc_id_formats(self) -> None:
        aadhaar = KYCDocument.model_validate(
            {
                "full_name": "SAMPLE USER",
                "document_type": "Aadhaar",
                "id_number": "9999 8888 7777",
                "date_of_birth": "1990-01-01",
                "address": "1 Sample Street",
            }
        )
        self.assertEqual(aadhaar.id_number, "999988887777")

        pan = KYCDocument.model_validate(
            {
                "full_name": "SAMPLE USER",
                "document_type": "PAN",
                "id_number": "aaaaa9999a",
                "date_of_birth": "01-02-1991",
                "address": "1 Sample Street",
            }
        )
        self.assertEqual(pan.id_number, "AAAAA9999A")

        with self.assertRaises(ValidationError):
            KYCDocument.model_validate(
                {
                    "full_name": "SAMPLE USER",
                    "document_type": "Passport",
                    "id_number": "NOPE",
                    "date_of_birth": "1992-03-03",
                    "address": "1 Sample Street",
                }
            )


if __name__ == "__main__":
    unittest.main()
