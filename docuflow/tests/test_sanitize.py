import env_setup  # noqa: F401
import unittest

from utils.sanitize import mask_aadhaar, mask_pan, sanitize_response

# Clearly fake identifiers in valid format — not issued government IDs.
FAKE_AADHAAR = "234567890123"
FAKE_PAN = "ABCDE1234F"


class SanitizeTests(unittest.TestCase):
    def test_mask_aadhaar_last_four(self) -> None:
        self.assertEqual(mask_aadhaar(FAKE_AADHAAR), "XXXX-XXXX-0123")
        self.assertEqual(mask_aadhaar("2345 6789 0123"), "XXXX-XXXX-0123")

    def test_mask_pan_first_five(self) -> None:
        self.assertEqual(mask_pan(FAKE_PAN), "XXXXX1234F")

    def test_sanitize_kyc_aadhaar_copy_only(self) -> None:
        raw = {
            "full_name": "Test User",
            "document_type": "Aadhaar",
            "id_number": FAKE_AADHAAR,
            "address": "1 Example Street",
        }
        masked = sanitize_response(raw)
        self.assertEqual(raw["id_number"], FAKE_AADHAAR)
        self.assertEqual(masked["id_number"], "XXXX-XXXX-0123")
        self.assertEqual(masked["full_name"], "Test User")

    def test_sanitize_kyc_pan(self) -> None:
        raw = {
            "full_name": "Test User",
            "document_type": "PAN",
            "id_number": FAKE_PAN,
        }
        masked = sanitize_response(raw)
        self.assertEqual(masked["id_number"], "XXXXX1234F")

    def test_sanitize_spaced_pan_and_numeric_aadhaar(self) -> None:
        pan = sanitize_response(
            {"document_type": "PAN Card", "id_number": "abcde 1234 f"},
            doc_hint="kyc",
        )
        self.assertEqual(pan["id_number"], "XXXXX1234F")
        aadhaar = sanitize_response(
            {"document_type": "Aadhaar Card", "id_number": 234567890123},
            doc_hint="kyc",
        )
        self.assertEqual(aadhaar["id_number"], "XXXX-XXXX-0123")

    def test_mask_ids_inside_kyc_text(self) -> None:
        from utils.sanitize import mask_ids_in_text

        text = mask_ids_in_text("ID number: 2345 6789 0123 and PAN ABCDE1234F")
        self.assertIn("XXXX-XXXX-0123", text)
        self.assertIn("XXXXX1234F", text)
        self.assertNotIn("ABCDE1234F", text)
        self.assertNotIn("2345 6789 0123", text)


if __name__ == "__main__":
    unittest.main()
