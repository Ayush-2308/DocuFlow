import env_setup  # noqa: F401
import unittest

from schemas.models import PipelineState
from db.supabase_client import (
    delete_document,
    insert_document,
    list_processed_documents,
    search_processed_documents,
    storage_backend,
)


class SqliteFallbackTests(unittest.TestCase):
    def test_sqlite_fallback_stores_and_lists_documents(self) -> None:
        self.assertEqual(storage_backend(), "sqlite")
        state = PipelineState(
            document_id="doc-fallback-1",
            file_path="C:/tmp/licence.pdf",
            doc_type_hint="kyc",
            raw_text="Name: Test User",
            extracted_data={"full_name": "Test User", "id_number": "ABC123"},
            confidence_score=0.9,
            validation_errors=[],
            category="identity",
            status="stored",
        )
        insert_document(state)
        rows = list_processed_documents()
        self.assertTrue(any(row["document_id"] == "doc-fallback-1" for row in rows))
        found = search_processed_documents("Test User", "kyc")
        self.assertTrue(found)
        self.assertEqual(found[0]["extracted_data"]["full_name"], "Test User")
        self.assertTrue(delete_document("doc-fallback-1"))
        leftover = list_processed_documents()
        self.assertTrue(all(row["document_id"] != "doc-fallback-1" for row in leftover))


if __name__ == "__main__":
    unittest.main()
