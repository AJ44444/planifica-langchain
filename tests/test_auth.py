import pytest
import os
import sys
from unittest.mock import patch, MagicMock
from bson import ObjectId

# Asegurar que el paquete app esté accesible en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from auth.auth_handler import verify_google_id_token, authenticate, Auth


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
async def test_auth_middleware_valid_token_existing_user():
    """
    Verifica el flujo completo del middleware authenticate() para un docente existente en MongoDB.
    """
    mock_google_payload = {
        "sub": "google_user_998877",
        "email": "docente.existente@escuela.edu.gt",
        "name": "Carlos Mendoza",
        "given_name": "Carlos",
        "family_name": "Mendoza"
    }
    mock_user_doc = {
        "_id": ObjectId("60d5ec49f1a2c8123456789a"),
        "google_id": "google_user_998877",
        "email": "docente.existente@escuela.edu.gt",
        "nombres": "Carlos",
        "apellidos": "Mendoza",
        "rol": "docente"
    }

    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.verify_google_id_token", return_value=mock_google_payload), \
         patch("auth.auth_handler.get_user_by_google_id", return_value=mock_user_doc):

        result = await authenticate(authorization="Bearer valid_id_token_xyz")

        assert result.get("identity") == "60d5ec49f1a2c8123456789a"
        assert result.get("is_authenticated") is True
        assert result.get("email") == "docente.existente@escuela.edu.gt"
        assert result.get("nombres") == "Carlos"
        assert result.get("rol") == "docente"


@pytest.mark.anyio
async def test_auth_middleware_valid_token_auto_register():
    """
    Verifica el flujo del middleware authenticate() al auto-registrar un docente nuevo.
    """
    mock_google_payload = {
        "sub": "google_user_new_123",
        "email": "nuevo.docente@escuela.edu.gt",
        "name": "Ana Juárez",
        "given_name": "Ana",
        "family_name": "Juárez",
        "picture": "https://example.com/photo.jpg"
    }
    created_user_doc = {
        "_id": ObjectId("60d5ec49f1a2c8123456789b"),
        "google_id": "google_user_new_123",
        "email": "nuevo.docente@escuela.edu.gt",
        "nombres": "Ana",
        "apellidos": "Juárez",
        "foto_perfil": "https://example.com/photo.jpg",
        "rol": "docente"
    }

    with patch("auth.auth_handler.check_db_connection", return_value=True), \
         patch("auth.auth_handler.verify_google_id_token", return_value=mock_google_payload), \
         patch("auth.auth_handler.get_user_by_google_id", return_value=None), \
         patch("auth.auth_handler.create_user_doc", return_value={"status": "success", "user": created_user_doc}):

        result = await authenticate(authorization="Bearer new_user_token")

        assert result.get("identity") == "60d5ec49f1a2c8123456789b"
        assert result.get("is_authenticated") is True
        assert result.get("email") == "nuevo.docente@escuela.edu.gt"


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
async def test_auth_middleware_db_inactive_500():
    """
    Verifica que si la comunicación con la base de datos no está activa, la autenticación falle
    respondiendo con un error HTTP 500 de Error Interno del Servidor.
    """
    with patch("auth.auth_handler.check_db_connection", return_value=False):
        with pytest.raises(Auth.exceptions.HTTPException) as exc_info:
            await authenticate(authorization="Bearer valid_id_token_xyz")

        assert exc_info.value.status_code == 500
        assert "Error Interno del Servidor" in exc_info.value.detail
