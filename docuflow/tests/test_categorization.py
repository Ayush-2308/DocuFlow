import env_setup  # noqa: F401
import unittest

from agents.categorization_agent import categorize


class CategorizationTests(unittest.TestCase):
    def test_travel(self) -> None:
        self.assertEqual(
            categorize({"vendor_name": "SAMPLE Marriott Hotel"}, "invoice"),
            "Travel Expense",
        )

    def test_office_supplies(self) -> None:
        self.assertEqual(
            categorize(
                {"vendor_name": "Demo", "line_items": [{"description": "Printer toner"}]},
                "invoice",
            ),
            "Office Supplies",
        )

    def test_meals(self) -> None:
        self.assertEqual(
            categorize({"merchant_name": "SAMPLE Starbucks Cafe"}, "receipt"),
            "Meals & Entertainment",
        )

    def test_software(self) -> None:
        self.assertEqual(
            categorize({"vendor_name": "SAMPLE Adobe subscription"}, "invoice"),
            "Software & Subscriptions",
        )

    def test_kyc_identity(self) -> None:
        self.assertEqual(
            categorize({"full_name": "SAMPLE USER", "document_type": "PAN"}, "kyc"),
            "Identity Verification",
        )

    def test_uncategorized(self) -> None:
        self.assertEqual(
            categorize({"vendor_name": "SAMPLE Ordinary Workshop"}, "invoice"),
            "Uncategorized",
        )


if __name__ == "__main__":
    unittest.main()
