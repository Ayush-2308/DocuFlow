import env_setup  # noqa: F401
import unittest
from unittest.mock import patch

from graph import REVIEW_CONFIDENCE_THRESHOLD, run_pipeline
from schemas.models import PipelineState


VALID_INVOICE = {
    "vendor_name": "SAMPLE Marriott Hotel",
    "invoice_number": "INV-1",
    "date": "2024-01-01",
    "line_items": [
        {"description": "Room", "quantity": 1, "unit_price": 100, "amount": 100}
    ],
    "subtotal": 100,
    "tax": 18,
    "total_amount": 118,
}


class GraphRoutingTests(unittest.TestCase):
    def test_errors_skip_storage(self) -> None:
        bad = dict(VALID_INVOICE)
        bad["total_amount"] = 999
        with (
            patch("graph.run_ocr", return_value="ocr text"),
            patch("graph.extract_fields", return_value=bad),
            patch("graph.insert_document") as insert,
            patch("graph.update_document_status") as update,
        ):
            state = run_pipeline("C:/tmp/sample.pdf", "invoice")
        self.assertEqual(state.status, "needs_review")
        insert.assert_not_called()
        update.assert_not_called()

    def test_low_confidence_skips_storage(self) -> None:
        with (
            patch("graph.run_ocr", return_value="ocr text"),
            patch("graph.extract_fields", return_value=VALID_INVOICE),
            patch(
                "graph.validate",
                return_value=(REVIEW_CONFIDENCE_THRESHOLD - 0.1, []),
            ),
            patch("graph.insert_document") as insert,
        ):
            state = run_pipeline("C:/tmp/sample.pdf", "invoice")
        self.assertEqual(state.status, "needs_review")
        insert.assert_not_called()

    def test_good_document_reaches_storage(self) -> None:
        with (
            patch("graph.run_ocr", return_value="ocr text"),
            patch("graph.extract_fields", return_value=VALID_INVOICE),
            patch("graph.insert_document") as insert,
            patch("graph.update_document_status") as update,
        ):
            state = run_pipeline("C:/tmp/sample.pdf", "invoice")
        self.assertEqual(state.status, "stored")
        self.assertEqual(state.category, "Travel Expense")
        insert.assert_called_once()
        self.assertIsInstance(insert.call_args.args[0], PipelineState)
        update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
