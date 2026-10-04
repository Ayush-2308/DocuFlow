import env_setup  # noqa: F401
import unittest
from datetime import date, timedelta

from agents.validation_agent import validate


class ValidationTests(unittest.TestCase):
    def test_invoice_required_fields(self) -> None:
        _score, errors = validate({}, "invoice")
        self.assertTrue(any("vendor_name" in item for item in errors))
        self.assertTrue(any("total_amount" in item for item in errors))

    def test_future_date(self) -> None:
        future = (date.today() + timedelta(days=10)).isoformat()
        data = {
            "vendor_name": "SAMPLE Vendor",
            "invoice_number": "INV-1",
            "date": future,
            "line_items": [
                {"description": "Item", "quantity": 1, "unit_price": 10, "amount": 10}
            ],
            "subtotal": 10,
            "tax": 0,
            "total_amount": 10,
        }
        _score, errors = validate(data, "invoice")
        self.assertTrue(any("future" in item for item in errors))

    def test_invoice_total_mismatch_beyond_tolerance(self) -> None:
        data = {
            "vendor_name": "SAMPLE Vendor",
            "invoice_number": "INV-2",
            "date": "2024-01-01",
            "line_items": [
                {"description": "Item", "quantity": 1, "unit_price": 100, "amount": 100}
            ],
            "subtotal": 100,
            "tax": 18,
            "total_amount": 999,
        }
        _score, errors = validate(data, "invoice")
        self.assertTrue(any("total_amount" in item for item in errors))

    def test_invoice_total_within_tolerance(self) -> None:
        data = {
            "vendor_name": "SAMPLE Vendor",
            "invoice_number": "INV-3",
            "date": "2024-01-01",
            "line_items": [
                {"description": "Item", "quantity": 1, "unit_price": 100, "amount": 100}
            ],
            "subtotal": 100,
            "tax": 18,
            "total_amount": 118.04,
        }
        _score, errors = validate(data, "invoice")
        self.assertFalse(any("total_amount" in item for item in errors))

    def test_aadhaar_format(self) -> None:
        good = {
            "full_name": "SAMPLE USER",
            "document_type": "Aadhaar",
            "id_number": "9999 8888 7777",
            "date_of_birth": "1990-01-01",
            "address": "1 Sample Street",
        }
        _score, errors = validate(good, "kyc")
        self.assertFalse(any("id_number" in item for item in errors))

        bad = dict(good)
        bad["id_number"] = "12345"
        _score, errors = validate(bad, "kyc")
        self.assertTrue(any("12 digits" in item for item in errors))

    def test_pan_and_passport_format(self) -> None:
        pan = {
            "full_name": "SAMPLE USER",
            "document_type": "PAN",
            "id_number": "AAAAA9999A",
            "date_of_birth": "1990-01-01",
            "address": "1 Sample Street",
        }
        _score, errors = validate(pan, "kyc")
        self.assertFalse(any("PAN" in item for item in errors))

        pan_bad = dict(pan)
        pan_bad["id_number"] = "1234"
        _score, errors = validate(pan_bad, "kyc")
        self.assertTrue(any("PAN" in item for item in errors))

        passport = dict(pan)
        passport["document_type"] = "Passport"
        passport["id_number"] = "Z9999999"
        _score, errors = validate(passport, "kyc")
        self.assertFalse(any("Passport" in item for item in errors))

        passport_bad = dict(passport)
        passport_bad["id_number"] = "INVALID"
        _score, errors = validate(passport_bad, "kyc")
        self.assertTrue(any("Passport" in item for item in errors))

    def test_confidence_score_calculation(self) -> None:
        perfect = {
            "merchant_name": "SAMPLE Shop",
            "date": "2024-01-01",
            "items": [{"description": "Item", "amount": 10}],
            "total_amount": 10,
        }
        score, errors = validate(perfect, "receipt")
        self.assertEqual(errors, [])
        self.assertEqual(score, 1.0)

        empty_score, empty_errors = validate({}, "receipt")
        self.assertGreater(len(empty_errors), 0)
        self.assertLess(empty_score, 1.0)
        self.assertGreaterEqual(empty_score, 0.0)


if __name__ == "__main__":
    unittest.main()
