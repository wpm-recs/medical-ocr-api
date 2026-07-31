"""API endpoint integration tests."""

import io
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestAPI:
    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_missing_file(self, client: TestClient):
        response = client.post("/ocr")
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "file_missing"

    def test_invalid_mime(self, client: TestClient):
        response = client.post(
            "/ocr",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "file_missing"

    @patch("app.api.ocr.process_document")
    def test_unsupported_document(self, mock_process, client: TestClient):
        from app.api.ocr import UnsupportedDocumentError
        mock_process.side_effect = UnsupportedDocumentError("unsupported_document_type")

        response = client.post(
            "/ocr",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "unsupported_document_type"

    def test_empty_filename(self, client: TestClient):
        response = client.post(
            "/ocr",
            files={"file": ("", io.BytesIO(b"content"), "application/pdf")},
        )
        assert response.status_code == 422
