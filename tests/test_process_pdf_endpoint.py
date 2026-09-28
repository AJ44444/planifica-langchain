import pytest
import os
import sys
import json
import hashlib
from unittest.mock import patch, AsyncMock, MagicMock
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ["JWT_SECRET"] = "test_jwt_secret_key_12345"
os.environ["SESSION_SECRET"] = "test_session_secret_key_12345"
os.environ["REFRESH_SECRET"] = "test_refresh_secret_key_12345"

from server import app
from core.tool_inputs import SaveCurricularStructureInput, Subarea, CompetenciaEspecifica, IndicadorLogro, Contenido


@pytest.fixture
def client():
    return TestClient(app)


def test_process_pdf_endpoint_options(client):
    """Verifies that OPTIONS /api/process-pdf returns 200 OK preflight response."""
    response = client.options("/api/process-pdf")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_pdf_endpoint_validation_missing_file_key(client):
    """Verifies that POST /api/process-pdf rejects missing file_key with 400 Bad Request."""
    response = client.post("/api/process-pdf", json={})
    assert response.status_code == 400
    assert "file_key" in response.json()["detail"]


def test_process_pdf_endpoint_success_and_idempotency(client):
    """Verifies that POST /api/process-pdf initiates PDF worker job and enforces idempotency."""
    file_key = "cnb/test_sample_pdf.pdf"
    mock_pdf_bytes = b"%PDF-1.4 sample pdf content for idempotency testing"
    expected_hash = hashlib.sha256(mock_pdf_bytes).hexdigest()
    job_id = f"job_{expected_hash[:16]}"

    mock_redis = AsyncMock()
    mock_redis.get.side_effect = lambda key: None  # first call returns no existing job

    with patch("api.process_pdf_handler.fetch_pdf_bytes_from_s3", return_value=mock_pdf_bytes), \
         patch("api.process_pdf_handler.get_env_variable", return_value="redis://localhost:6379"), \
         patch("api.process_pdf_handler.from_url", return_value=mock_redis):

        response = client.post("/api/process-pdf", json={"file_key": file_key})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["job_id"] == job_id

        # Verify Redis calls
        mock_redis.xadd.assert_called_once()
        mock_redis.publish.assert_called_once()

    # Second call for idempotency test: mock existing job in Redis
    existing_job_data = {
        "id": job_id,
        "file_key": file_key,
        "file_hash": expected_hash,
        "main_task": "Procesar Currículum",
        "subtask": "Procesamiento en progreso",
        "status": "progress"
    }

    async def mock_redis_get(key):
        if key == f"idempotency:process_pdf:{file_key}:{expected_hash}":
            return job_id
        if key == f"job:{job_id}:status":
            return json.dumps(existing_job_data, ensure_ascii=False)
        return None

    mock_redis_idempotent = AsyncMock()
    mock_redis_idempotent.get.side_effect = mock_redis_get

    with patch("api.process_pdf_handler.fetch_pdf_bytes_from_s3", return_value=mock_pdf_bytes), \
         patch("api.process_pdf_handler.get_env_variable", return_value="redis://localhost:6379"), \
         patch("api.process_pdf_handler.from_url", return_value=mock_redis_idempotent):

        response_idempotent = client.post("/api/process-pdf", json={"file_key": file_key})
        assert response_idempotent.status_code == 200
        data_idempotent = response_idempotent.json()
        assert data_idempotent["status"] == "success"
        assert data_idempotent["job_id"] == job_id
        assert "ya fue procesado" in data_idempotent["message"]

        # Redis xadd should NOT be called on idempotent request
        mock_redis_idempotent.xadd.assert_not_called()
