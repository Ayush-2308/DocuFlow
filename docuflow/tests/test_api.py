import env_setup  # noqa: F401
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import _upload_limiter, app
from schemas.models import PipelineState

TINY_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        _upload_limiter.reset()
        self.client = TestClient(app)
        fake_state = PipelineState(
            document_id="00000000-0000-0000-0000-000000000099",
            file_path="upload.pdf",
            status="stored",
        )
        self._pipeline = patch("main.run_pipeline", return_value=fake_state)
        self._pipeline.start()

    def tearDown(self) -> None:
        self._pipeline.stop()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("llm_provider", body)

    def test_upload_rejects_bad_extension(self) -> None:
        response = self.client.post(
            "/upload",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"doc_type_hint": "invoice"},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_rejects_oversized_file(self) -> None:
        payload = TINY_PDF + (b"x" * (1024 * 1024 + 10))
        response = self.client.post(
            "/upload",
            files={"file": ("big.pdf", payload, "application/pdf")},
            data={"doc_type_hint": "invoice"},
        )
        self.assertEqual(response.status_code, 413)

    def test_upload_accepts_pdf_and_png(self) -> None:
        pdf = self.client.post(
            "/upload",
            files={"file": ("ok.pdf", TINY_PDF, "application/pdf")},
            data={"doc_type_hint": "invoice"},
        )
        self.assertEqual(pdf.status_code, 200)
        png = self.client.post(
            "/upload",
            files={"file": ("ok.png", TINY_PNG, "image/png")},
            data={"doc_type_hint": "receipt"},
        )
        self.assertEqual(png.status_code, 200)

    def test_upload_rate_limit(self) -> None:
        files = {"file": ("ok.pdf", TINY_PDF, "application/pdf")}
        data = {"doc_type_hint": "invoice"}
        codes = [
            self.client.post("/upload", files=files, data=data).status_code
            for _ in range(11)
        ]
        self.assertIn(429, codes)
        self.assertGreaterEqual(codes.count(200), 10)

    def test_search_unauthorized_without_key(self) -> None:
        response = self.client.get("/search", params={"query": "SAMPLE"})
        self.assertEqual(response.status_code, 401)

    def test_search_empty_query(self) -> None:
        response = self.client.get(
            "/search",
            params={"query": "  "},
            headers={"X-API-Key": "test-search-key"},
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_unauthorized_without_key(self) -> None:
        response = self.client.request(
            "DELETE",
            "/documents",
            json={"document_ids": ["00000000-0000-0000-0000-000000000001"]},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
