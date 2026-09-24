import pytest
import os
import sys
import json
import asyncio
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.vector_tool import dispatch_subarea_vectorization, generate_and_store_subarea_embeddings
from workers.vectorization_worker import VectorizationWorker
from server import app


def test_dispatch_subarea_vectorization_tool_success():
    """Verifies that dispatch_subarea_vectorization tool dispatches an event via Redis Stream."""
    mock_redis_client = MagicMock()
    mock_redis_client.xadd.return_value = "1727100000000-0"

    with patch("tools.vector_tool.get_env_variable", return_value="redis://localhost:6379"), \
         patch("redis.Redis.from_url", return_value=mock_redis_client):

        res_str = dispatch_subarea_vectorization.invoke({"id_subarea": "60d5ec49f1a2c81234567899"})
        res = json.loads(res_str)

        assert res["status"] == "success"
        assert res["id_subarea"] == "60d5ec49f1a2c81234567899"
        mock_redis_client.xadd.assert_called_once_with("stream:vectorization", {"id_subarea": "60d5ec49f1a2c81234567899"})


def test_vectorization_worker_process_message_publishes_status_only():
    """
    Verifies that VectorizationWorker publishes in_progress and completed status
    without including result data.
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
            await worker.process_message("1727100000000-0", {"id_subarea": "60d5ec49f1a2c81234567899"})

            assert mock_redis.set.call_count == 2
            assert mock_redis.publish.call_count == 2

            # Verify calls contain ONLY id_subarea and status (NO data/results)
            first_call_args = mock_redis.set.call_args_list[0][0]
            first_payload = json.loads(first_call_args[1])
            assert first_payload == {"id_subarea": "60d5ec49f1a2c81234567899", "status": "in_progress"}

            second_call_args = mock_redis.set.call_args_list[1][0]
            second_payload = json.loads(second_call_args[1])
            assert second_payload == {"id_subarea": "60d5ec49f1a2c81234567899", "status": "completed"}
            assert "result" not in second_payload
            assert "data" not in second_payload

    asyncio.run(run_test())


def test_notifications_sse_endpoint_route_registered():
    """Verifies that /api/notifications route exists in the Starlette app."""
    route_paths = [route.path for route in app.routes]
    assert "/api/notifications" in route_paths
