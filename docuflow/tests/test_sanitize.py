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


if __name__ == "__main__":
    unittest.main()
