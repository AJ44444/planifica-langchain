import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ["JWT_SECRET"] = "test_jwt_secret_key_12345"
os.environ["SESSION_SECRET"] = "test_session_secret_key_12345"
os.environ["REFRESH_SECRET"] = "test_refresh_secret_key_12345"
os.environ["AWS_S3_BUCKET_NAME"] = "test-cnb-bucket"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test_access_key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test_secret_key"

from server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_generate_presigned_url_endpoint_success(client):
    """Verifies GET /api/generate-url generates S3 presigned POST URL with conditions and 5-min expiration."""
    mock_presigned_post = {
        "url": "https://test-cnb-bucket.s3.amazonaws.com",
        "fields": {
            "key": "cnb/12345678_test.pdf",
            "Content-Type": "application/pdf",
            "policy": "mock_policy",
            "x-amz-signature": "mock_sig"
        }
    }

    mock_s3_client = MagicMock()
    mock_s3_client.generate_presigned_post.return_value = mock_presigned_post

    with patch("api.upload_handler.get_s3_client", return_value=(mock_s3_client, "test-cnb-bucket")):
        response = client.get("/api/generate-url")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["url"] == "https://test-cnb-bucket.s3.amazonaws.com"
        assert data["fields"]["Content-Type"] == "application/pdf"
        assert data["bucket"] == "test-cnb-bucket"
        assert data["expires_in"] == 300
        assert data["file_key"].startswith("cnb/")
        assert data["file_key"].endswith(".pdf")

        # Verify call arguments to generate_presigned_post
        mock_s3_client.generate_presigned_post.assert_called_once()
        kwargs = mock_s3_client.generate_presigned_post.call_args.kwargs
        assert kwargs["Bucket"] == "test-cnb-bucket"
        assert kwargs["ExpiresIn"] == 300
        assert kwargs["Fields"]["Content-Type"] == "application/pdf"
        assert kwargs["Conditions"] == [
            {"Content-Type": "application/pdf"},
            ["content-length-range", 1, 10485760]
        ]
