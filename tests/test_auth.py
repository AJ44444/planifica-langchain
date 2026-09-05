import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from bson import ObjectId

# Ensure app package is accessible in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ["JWT_SECRET"] = "test_jwt_secret_key_12345"

from auth.auth_handler import (
    verify_google_id_token,
    create_access_token,
    create_refresh_token,
    verify_project_access_token,
    exchange_google_token_for_session,
    refresh_access_token_session,
    authenticate,
    Auth,
)


def test_create_and_verify_access_token_5_min_expiration():
    """
    Verifies that create_access_token creates a signed JWT with an exact 5-minute expiration (300 s).
    """
    token = create_access_token(user_id="60d5ec49f1a2c8123456789a", email="test@escuela.edu.gt", nombres="Docente Test")
    payload = verify_project_access_token(token)

    assert payload["sub"] == "60d5ec49f1a2c8123456789a"
    assert payload["email"] == "test@escuela.edu.gt"
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 300


def test_exchange_google_token_for_session_returns_jwt_and_refresh_token():
    """
    Verifies that exchange_google_token_for_session verifies Google token and issues access and refresh tokens.
    """
    mock_google_payload = {
        "sub": "google_user_exchange_123",
        "email": "docente.session@escuela.edu.gt",
        "name": "Lucía Morales",
        "given_name": "Lucía",
        "family_name": "Morales"
    }
    mock_user_doc = {
        "_id": ObjectId("60d5ec49f1a2c8123456789c"),
        "google_id": "google_user_exchange_123",
        "email": "docente.session@escuela.edu.gt",
        "nombres": "Lucía",
        "apellidos": "Morales",
        "rol": "docente"
    }

    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.verify_google_id_token", return_value=mock_google_payload), \
         patch("auth.auth_handler.get_user_by_google_id", return_value=mock_user_doc), \
         patch("auth.auth_handler.save_refresh_token", return_value=True):

        session = exchange_google_token_for_session("valid_google_id_token_test")

        assert "access_token" in session
        assert "refresh_token" in session
        assert session["expires_in"] == 300
        assert session["token_type"] == "Bearer"
        assert session["user"]["id_usuario"] == "60d5ec49f1a2c8123456789c"

        jwt_payload = verify_project_access_token(session["access_token"])
        assert jwt_payload["sub"] == "60d5ec49f1a2c8123456789c"


def test_refresh_access_token_session_success():
    """
    Verifies that refresh_access_token_session exchanges a valid refresh token for a new Access Token.
    """
    mock_refresh_doc = {
        "_id": "token_doc_id",
        "id_usuario": "60d5ec49f1a2c8123456789c",
        "refresh_token": "valid_refresh_token_hex_123",
        "expires_at": 9999999999.0
    }
    mock_user_doc = {
        "_id": ObjectId("60d5ec49f1a2c8123456789c"),
        "email": "docente.session@escuela.edu.gt",
        "nombres": "Lucía",
        "rol": "docente"
    }

    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.get_refresh_token_doc", return_value=mock_refresh_doc), \
         patch("auth.auth_handler.get_user_profile_doc", return_value=mock_user_doc):

        new_session = refresh_access_token_session("valid_refresh_token_hex_123")

        assert "access_token" in new_session
        assert new_session["expires_in"] == 300
        jwt_payload = verify_project_access_token(new_session["access_token"])
        assert jwt_payload["sub"] == "60d5ec49f1a2c8123456789c"


@pytest.mark.anyio
async def test_auth_middleware_with_cookie_access_token():
    """
    Verifies that authenticate() middleware accepts Access Token from Cookie header.
    """
    access_token = create_access_token(
        user_id="60d5ec49f1a2c8123456789a",
        email="docente.cookie@escuela.edu.gt",
        nombres="Marta Cookie",
        rol="docente"
    )

    result = await authenticate(headers={"cookie": f"access_token={access_token}"})

    assert result.get("identity") == "60d5ec49f1a2c8123456789a"
    assert result.get("is_authenticated") is True
    assert result.get("email") == "docente.cookie@escuela.edu.gt"


@pytest.mark.anyio
async def test_auth_middleware_rejects_bearer_token_without_cookie():
    """
    Verifies that authenticate() middleware rejects Bearer header token as it only accepts cookies.
    """
    access_token = create_access_token(
        user_id="60d5ec49f1a2c8123456789a",
        email="docente.bearer@escuela.edu.gt",
        nombres="Marta Bearer",
        rol="docente"
    )

    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(authorization=f"Bearer {access_token}")

    assert exc_info.value.status_code == 401
    assert "Access Denied" in exc_info.value.detail


@pytest.mark.anyio
async def test_auth_middleware_allows_public_auth_routes():
    """
    Verifies that authenticate() middleware allows public routes without requiring access_token cookie.
    """
    result_login = await authenticate(path="/auth/login")
    assert result_login["identity"] == "anonymous"
    assert result_login["is_authenticated"] is False

    result_refresh = await authenticate(path="/auth/refresh")
    assert result_refresh["identity"] == "anonymous"
    assert result_refresh["is_authenticated"] is False

    result_logout = await authenticate(path="/auth/logout")
    assert result_logout["identity"] == "anonymous"
    assert result_logout["is_authenticated"] is False

    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(path="/threads")
    assert exc_info.value.status_code == 401


@pytest.mark.anyio
async def test_server_endpoints_set_secure_httponly_cookies():
    """
    Verifies that /auth/login and /auth/refresh return secure HttpOnly, SameSite=lax, and Secure cookies.
    """
    from starlette.testclient import TestClient
    from server import app

    client = TestClient(app)

    mock_google_payload = {
        "sub": "google_user_cookies_123",
        "email": "docente.cookies@escuela.edu.gt",
        "name": "Lucía Morales",
        "given_name": "Lucía",
        "family_name": "Morales"
    }
    mock_user_doc = {
        "_id": ObjectId("60d5ec49f1a2c8123456789d"),
        "google_id": "google_user_cookies_123",
        "email": "docente.cookies@escuela.edu.gt",
        "nombres": "Lucía",
        "apellidos": "Morales",
        "rol": "docente"
    }

    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.verify_google_id_token", return_value=mock_google_payload), \
         patch("auth.auth_handler.get_user_by_google_id", return_value=mock_user_doc), \
         patch("auth.auth_handler.save_refresh_token", return_value=True):

        response = client.post("/auth/login", json={"id_token": "valid_google_token_123"})
        assert response.status_code == 200
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

        set_cookie_headers = response.headers.get_list("set-cookie")
        assert any("httponly" in h.lower() for h in set_cookie_headers)
        assert any("samesite=lax" in h.lower() for h in set_cookie_headers)
        assert any("secure" in h.lower() for h in set_cookie_headers)


@pytest.mark.anyio
async def test_auth_middleware_rejects_non_project_tokens():
    """
    Verifies that authenticate() middleware rejects non-project JWT tokens.
    """
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(authorization="Bearer raw_invalid_or_google_token_123")

    assert exc_info.value.status_code == 401
    assert "Access Denied" in exc_info.value.detail


def test_verify_google_id_token_valid():
    """
    Verifies that verify_google_id_token returns verified Google OAuth payload.
    """
    mock_payload = {
        "sub": "112233445566778899",
        "email": "docente.cnb@educacion.gob.gt",
        "name": "María López",
        "given_name": "María",
        "family_name": "López",
        "picture": "https://lh3.googleusercontent.com/a/sample_photo.jpg"
    }

    with patch("auth.auth_handler.google_id_token_verifier.verify_oauth2_token", return_value=mock_payload):
        payload = verify_google_id_token("mocked_google_id_token_valid")
        assert payload.get("sub") == "112233445566778899"
        assert payload.get("email") == "docente.cnb@educacion.gob.gt"
        assert payload.get("name") == "María López"


def test_verify_google_id_token_invalid():
    """
    Verifies that verify_google_id_token raises ValueError when Google token is invalid or expired.
    """
    with patch("auth.auth_handler.google_id_token_verifier.verify_oauth2_token", side_effect=ValueError("Token expirado")):
        with pytest.raises(ValueError) as exc_info:
            verify_google_id_token("invalid_expired_token")
        assert "Error verifying Google OAuth token" in str(exc_info.value)


@pytest.mark.anyio
async def test_auth_middleware_missing_header():
    """
    Verifies that authenticate() rejects requests without authorization headers.
    """
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(authorization=None, headers=None)
    assert exc_info.value.status_code == 401
    assert "Access Denied" in exc_info.value.detail


@pytest.mark.anyio
async def test_auth_middleware_db_inactive_401():
    """
    Verifies that if database communication is inactive, authentication fails with HTTP 401 Access Denied.
    """
    with patch("auth.auth_handler.check_db_connection", return_value=False):
        with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
            await authenticate(authorization="Bearer valid_id_token_xyz")

        assert exc_info.value.status_code == 401
        assert "Access Denied" in exc_info.value.detail


@pytest.mark.anyio
async def test_auth_middleware_user_missing_id_401():
    """
    Verifies that if returned database user is invalid or missing _id, authentication raises HTTP 401.
    """
    mock_google_payload = {
        "sub": "google_user_no_id",
        "email": "invalid.user@escuela.edu.gt"
    }
    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.verify_google_id_token", return_value=mock_google_payload), \
         patch("auth.auth_handler.get_user_by_google_id", return_value=None), \
         patch("auth.auth_handler.create_user_doc", return_value={"status": "error", "user": None}):

        with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
            await authenticate(authorization="Bearer token_invalid_user")

        assert exc_info.value.status_code == 401
        assert "Access Denied" in exc_info.value.detail


def test_get_env_variable_success():
    """
    Verifies that get_env_variable returns value of a configured environment variable.
    """
    from core.config import get_env_variable
    with patch.dict(os.environ, {"TEST_CONFIG_VAR": "valor_prueba_123"}):
        val = get_env_variable("TEST_CONFIG_VAR")
        assert val == "valor_prueba_123"


def test_get_env_variable_missing_raises_value_error():
    """
    Verifies that get_env_variable raises ValueError if environment variable is missing or empty.
    """
    from core.config import get_env_variable
    with patch.dict(os.environ, {}, clear=True):
        if "MISSING_VAR_XYZ" in os.environ:
            del os.environ["MISSING_VAR_XYZ"]
        with pytest.raises(ValueError) as exc_info:
            get_env_variable("MISSING_VAR_XYZ")
        assert "MISSING_VAR_XYZ" in str(exc_info.value)
        assert "is not configured" in str(exc_info.value)


@pytest.mark.anyio
async def test_auth_on_resource_isolation_between_users():
    """
    Verifies that @auth.on.threads and @auth.on.store decorators strictly isolate resources between User A and User B.
    """
    from auth.auth_handler import authorize_threads, authorize_store

    class MockUser:
        def __init__(self, identity: str):
            self.identity = identity
            self.is_authenticated = True

    class MockCtx:
        def __init__(self, user_identity: str):
            self.user = MockUser(user_identity)

    ctx_user_a = MockCtx("user_id_A_123")
    ctx_user_b = MockCtx("user_id_B_456")

    payload_a = {}
    filters_a = await authorize_threads(ctx_user_a, payload_a)
    assert payload_a["metadata"]["owner"] == "user_id_A_123"
    assert filters_a == {"owner": "user_id_A_123"}

    payload_b = {}
    filters_b = await authorize_threads(ctx_user_b, payload_b)
    assert payload_b["metadata"]["owner"] == "user_id_B_456"
    assert filters_b == {"owner": "user_id_B_456"}

    assert filters_a["owner"] != filters_b["owner"]

    store_val_a = {"namespace": ("memories", "pref")}
    await authorize_store(ctx_user_a, store_val_a)
    assert store_val_a["namespace"] == ("user_id_A_123", "memories", "pref")

    store_val_b = {"namespace": ("memories", "pref")}
    await authorize_store(ctx_user_b, store_val_b)
    assert store_val_b["namespace"] == ("user_id_B_456", "memories", "pref")

    assert store_val_a["namespace"] != store_val_b["namespace"]
