import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from bson import ObjectId

# Asegurar que el paquete app esté accesible en sys.path
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
    Verifica que create_access_token cree un JWT firmado con expiración exacta de 5 minutos (300 s).
    """
    token = create_access_token(user_id="60d5ec49f1a2c8123456789a", email="test@escuela.edu.gt", nombres="Docente Test")
    payload = verify_project_access_token(token)

    assert payload["sub"] == "60d5ec49f1a2c8123456789a"
    assert payload["email"] == "test@escuela.edu.gt"
    assert payload["type"] == "access"
    assert payload["exp"] - payload["iat"] == 300


def test_exchange_google_token_for_session_returns_jwt_and_refresh_token():
    """
    Verifica que exchange_google_token_for_session verifique el token de Google y emita:
    1. access_token de 5 min (expires_in: 300).
    2. refresh_token de 7 días.
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

        # Verificar que el access_token retornado sea válido y tenga los 5 min
        jwt_payload = verify_project_access_token(session["access_token"])
        assert jwt_payload["sub"] == "60d5ec49f1a2c8123456789c"


def test_refresh_access_token_session_success():
    """
    Verifica que refresh_access_token_session intercambie un refresh token válido (7 días) por un nuevo Access Token (5 min).
    Usa los campos estándar id_usuario, refresh_token, fecha_creacion, fecha_expiracion.
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
    Verifica que el middleware authenticate() acepte el Access Token desde el encabezado Cookie.
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
    Verifica que el middleware authenticate() rechace encabezados Bearer token ya que únicamente acepta cookies.
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
    assert "Acceso Denegado" in exc_info.value.detail


@pytest.mark.anyio
async def test_server_endpoints_set_secure_httponly_cookies():
    """
    Verifica que /auth/login y /auth/refresh devuelvan las cookies seguras HttpOnly, SameSite=lax y Secure.
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

        # Verificar encabezados Set-Cookie
        set_cookie_headers = response.headers.get_list("set-cookie")
        assert any("httponly" in h.lower() for h in set_cookie_headers)
        assert any("samesite=lax" in h.lower() for h in set_cookie_headers)
        assert any("secure" in h.lower() for h in set_cookie_headers)


@pytest.mark.anyio
async def test_auth_middleware_rejects_non_project_tokens():
    """
    Verifica que el middleware authenticate() rechace cualquier token que no sea un JWT propio del proyecto.
    """
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(authorization="Bearer raw_invalid_or_google_token_123")

    assert exc_info.value.status_code == 401
    assert "Acceso Denegado" in exc_info.value.detail


def test_verify_google_id_token_valid():
    """
    Verifica que verify_google_id_token retorne el payload verificado de Google OAuth.
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
    Verifica que verify_google_id_token eleve ValueError cuando el token de Google es inválido o expirado.
    """
    with patch("auth.auth_handler.google_id_token_verifier.verify_oauth2_token", side_effect=ValueError("Token expirado")):
        with pytest.raises(ValueError) as exc_info:
            verify_google_id_token("invalid_expired_token")
        assert "Error en la verificación del token de Google OAuth" in str(exc_info.value)


@pytest.mark.anyio
async def test_auth_middleware_missing_header():
    """
    Verifica que authenticate() rechace peticiones sin encabezado Authorization.
    """
    with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
        await authenticate(authorization=None, headers=None)
    assert exc_info.value.status_code == 401
    assert "Acceso Denegado" in exc_info.value.detail


@pytest.mark.anyio
async def test_auth_middleware_db_inactive_401():
    """
    Verifica que si la comunicación con la base de datos no está activa, la autenticación falle
    respondiendo con un error HTTP 401 de Acceso Denegado.
    """
    with patch("auth.auth_handler.check_db_connection", return_value=False):
        with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
            await authenticate(authorization="Bearer valid_id_token_xyz")

        assert exc_info.value.status_code == 401
        assert "Acceso Denegado" in exc_info.value.detail


@pytest.mark.anyio
async def test_auth_middleware_user_missing_id_401():
    """
    Verifica que si el usuario retornado de la BD no es válido o carece de _id, la autenticación
    eleve un error HTTP 401 de Acceso Denegado.
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
        assert "Acceso Denegado" in exc_info.value.detail


def test_get_env_variable_success():
    """
    Verifica que get_env_variable retorne el valor de una variable de entorno configurada.
    """
    from core.config import get_env_variable
    with patch.dict(os.environ, {"TEST_CONFIG_VAR": "valor_prueba_123"}):
        val = get_env_variable("TEST_CONFIG_VAR")
        assert val == "valor_prueba_123"


def test_get_env_variable_missing_raises_value_error():
    """
    Verifica que get_env_variable eleve un ValueError si la variable de entorno no está configurada o está vacía.
    """
    from core.config import get_env_variable
    with patch.dict(os.environ, {}, clear=True):
        if "MISSING_VAR_XYZ" in os.environ:
            del os.environ["MISSING_VAR_XYZ"]
        with pytest.raises(ValueError) as exc_info:
            get_env_variable("MISSING_VAR_XYZ")
        assert "MISSING_VAR_XYZ" in str(exc_info.value)
        assert "no está configurada" in str(exc_info.value)
