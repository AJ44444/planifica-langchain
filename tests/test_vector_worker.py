import pytest
import os
import sys
import json
import asyncio
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.vector_tool import generate_and_store_subarea_embeddings
from workers.vectorization_worker import VectorizationWorker
from server import app


def test_vectorization_worker_process_message_publishes_status_only():
    """
    Verifies that VectorizationWorker publishes progress and finish status
    using unified job structure without including raw data.
    """
    async def run_test():
        with patch("workers.vectorization_worker.get_env_variable", return_value="redis://localhost:6379"):
            worker = VectorizationWorker()
        mock_redis = MagicMock()

        async def mock_set(key, val):
            pass

        async def mock_publish(channel, msg):
            pass

        async def mock_xack(stream, group, msg_id):
            pass

        mock_redis.set = MagicMock(side_effect=mock_set)
        mock_redis.publish = MagicMock(side_effect=mock_publish)
        mock_redis.xack = MagicMock(side_effect=mock_xack)

        worker.redis = mock_redis

        with patch("workers.vectorization_worker.generate_and_store_subarea_embeddings", return_value='{"status": "success", "vectores_actualizados": 5}'):
            await worker.process_message("1727100000000-0", {"action": "vectorize", "id_subarea": "60d5ec49f1a2c81234567899"})

            assert mock_redis.set.call_count == 2
            assert mock_redis.publish.call_count == 2

            # Verify calls contain unified job structure
            first_call_args = mock_redis.set.call_args_list[0][0]
            first_payload = json.loads(first_call_args[1])
            assert first_payload["status"] == "progress"
            assert "Generando vectores" in first_payload["subtask"]

            second_call_args = mock_redis.set.call_args_list[1][0]
            second_payload = json.loads(second_call_args[1])
            assert second_payload["status"] == "finish"
            assert "result" not in second_payload
            assert "data" not in second_payload

    asyncio.run(run_test())


def test_notifications_sse_endpoint_route_registered():
    """Verifies that /api/notifications route exists in the Starlette app."""
    route_paths = [route.path for route in app.routes]
    assert "/api/notifications" in route_paths


def test_is_google_rate_limit_error():
    """Verifies that is_google_rate_limit_error detects 429 and ResourceExhausted errors correctly."""
    from tools.vector_tool import is_google_rate_limit_error

    class ResourceExhausted(Exception):
        pass

    assert is_google_rate_limit_error(ResourceExhausted("429 ResourceExhausted: Quota exceeded"))
    assert is_google_rate_limit_error(Exception("429 Too Many Requests"))
    assert is_google_rate_limit_error(Exception("Quota exceeded for api google"))
    assert not is_google_rate_limit_error(ValueError("Invalid argument"))


def test_vectorization_worker_pauses_on_google_rate_limit():
    """
    Verifies that VectorizationWorker sets status to 'paused' and stops execution
    when a Google API rate limit error (429 / ResourceExhausted) is encountered.
    """
    async def run_test():
        with patch("workers.vectorization_worker.get_env_variable", return_value="redis://localhost:6379"):
            worker = VectorizationWorker()
        mock_redis = MagicMock()

        async def mock_set(key, val):
            pass

        async def mock_publish(channel, msg):
            pass

        async def mock_xack(stream, group, msg_id):
            pass

        mock_redis.set = MagicMock(side_effect=mock_set)
        mock_redis.publish = MagicMock(side_effect=mock_publish)
        mock_redis.xack = MagicMock(side_effect=mock_xack)

        worker.redis = mock_redis
        worker.running = True

        class ResourceExhausted(Exception):
            pass

        rate_limit_exc = ResourceExhausted("429 ResourceExhausted: Quota exceeded for quota metric 'Generate Content API requests'")

        with patch("workers.vectorization_worker.generate_and_store_subarea_embeddings", side_effect=rate_limit_exc):
            await worker.process_message("1727100000000-0", {"action": "vectorize", "job_id": "job_123", "id_subarea": "60d5ec49f1a2c81234567899", "nombre_subarea": "Matemáticas"})

            assert mock_redis.set.call_count == 2
            second_call_args = mock_redis.set.call_args_list[1][0]
            second_payload = json.loads(second_call_args[1])

            assert second_payload["status"] == "paused"
            assert "Límite de cuota" in second_payload["subtask"]
            assert worker.running is False

    asyncio.run(run_test())


def test_pdf_worker_pauses_on_google_rate_limit():
    """
    Verifies that PdfProcessingWorker sets status to 'paused' and stops execution
    when a Google API rate limit error is encountered during LLM invocation.
    """
    async def run_test():
        from workers.pdf_worker import PdfProcessingWorker

        with patch("workers.pdf_worker.get_env_variable", return_value="redis://localhost:6379"):
            worker = PdfProcessingWorker()
        mock_redis = MagicMock()

        async def mock_set(key, val):
            pass

        async def mock_publish(channel, msg):
            pass

        async def mock_xack(stream, group, msg_id):
            pass

        mock_redis.set = MagicMock(side_effect=mock_set)
        mock_redis.publish = MagicMock(side_effect=mock_publish)
        mock_redis.xack = MagicMock(side_effect=mock_xack)

        worker.redis = mock_redis
        worker.running = True

        class ResourceExhausted(Exception):
            pass

        rate_limit_exc = ResourceExhausted("429 ResourceExhausted: Quota exceeded")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = rate_limit_exc
        worker._llm = mock_llm

        fake_areas = [{"clean_name": "Matemáticas", "content": "Contenido del área"}]

        with patch("workers.pdf_worker.fetch_pdf_bytes_from_s3", return_value=b"%PDF-fake"), \
             patch("workers.pdf_worker.convert_pdf_bytes", return_value="Fake pdf content"), \
             patch("workers.pdf_worker.extract_career_name", return_value="Bachillerato"), \
             patch("workers.pdf_worker.parse_curricular_areas", return_value=fake_areas):

            await worker.process_pdf_job(job_id="job_pdf_999", file_key="cnb/test.pdf", file_hash="hash123")

            paused_calls = [
                json.loads(call[0][1]) for call in mock_redis.set.call_args_list
                if json.loads(call[0][1]).get("status") == "paused"
            ]

            assert len(paused_calls) > 0
            assert paused_calls[0]["status"] == "paused"
            assert "Límite de cuota" in paused_calls[0]["subtask"]
            assert worker.running is False

    asyncio.run(run_test())

