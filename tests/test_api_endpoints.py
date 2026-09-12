import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
os.environ["JWT_SECRET"] = "test_jwt_secret_key_12345"
os.environ["SESSION_SECRET"] = "test_session_secret_key_12345"
os.environ["REFRESH_SECRET"] = "test_refresh_secret_key_12345"

from server import app
from auth.auth_handler import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def test_verify_session_endpoint_unauthenticated(client):
    """Verifies that GET /auth/verify returns 401 Unauthorized when no cookie is provided."""
    response = client.get("/auth/verify")
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]


def test_verify_session_endpoint_rejects_bearer_token(client):
    """Verifies that GET /auth/verify rejects Bearer token in Authorization header when cookie is missing."""
    token = create_access_token(user_id="60d5ec49f1a2c8123456789a", email="docente.verify@escuela.edu.gt")
    response = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]


def test_verify_session_endpoint_authenticated(client):
    """Verifies that GET /auth/verify returns 200 OK with user info when a valid session_id cookie is provided."""
    user_id = "60d5ec49f1a2c8123456789a"
    token = create_access_token(user_id=user_id, email="docente.verify@escuela.edu.gt", nombres="Docente Verify")

    mock_jwt = {
        "sub": user_id,
        "email": "docente.verify@escuela.edu.gt",
        "nombres": "Docente Verify",
        "rol": "docente"
    }

    with patch("api.auth_handler.get_or_refresh_session", return_value=mock_jwt):
        client.cookies.set("session_id", "valid_session_cookie_123")
        response = client.get("/auth/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert data["authenticated"] is True
        assert data["user"]["id_usuario"] == user_id
        assert data["user"]["email"] == "docente.verify@escuela.edu.gt"


def test_get_paginated_lesson_plans_endpoint_unauthenticated(client):
    """Verifies that /api/lesson-plans rejects unauthenticated requests with 401."""
    response = client.get("/api/lesson-plans")
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]


def test_get_paginated_lesson_plans_endpoint_success(client):
    """Verifies that /api/lesson-plans returns paginated history for authenticated user."""
    user_id = "60d5ec49f1a2c8123456789a"
    mock_jwt = {
        "sub": user_id,
        "email": "docente@escuela.edu.gt"
    }

    mock_res_str = json.dumps({
        "status": "success",
        "total_registros": 1,
        "total_paginas": 1,
        "pagina_actual": 1,
        "registros_por_pagina": 10,
        "planificaciones": [{"_id": "60d5ec49f1a2c8123456789b"}]
    })

    with patch("api.lesson_plan_handler.get_or_refresh_session", return_value=mock_jwt), \
         patch("api.lesson_plan_handler.get_paginated_lesson_plans.func", return_value=mock_res_str):
        client.cookies.set("session_id", "valid_session_cookie_123")
        response = client.get("/api/lesson-plans?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["planificaciones"]) == 1


def test_get_lesson_plan_details_endpoint_unauthenticated(client):
    """Verifies that /api/lesson-plans/{id_planificacion} rejects unauthenticated requests with 401."""
    response = client.get("/api/lesson-plans/60d5ec49f1a2c8123456789b")
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]


def test_get_lesson_plan_details_endpoint_success(client):
    """Verifies that /api/lesson-plans/{id_planificacion} returns full details."""
    user_id = "60d5ec49f1a2c8123456789a"
    plan_id = "60d5ec49f1a2c8123456789b"
    mock_jwt = {
        "sub": user_id,
        "email": "docente@escuela.edu.gt"
    }

    mock_res_str = json.dumps({
        "status": "success",
        "planificacion": {"_id": plan_id},
        "instrumentos_evaluacion": [],
        "recursos_multimodales": []
    })

    with patch("api.lesson_plan_handler.get_or_refresh_session", return_value=mock_jwt), \
         patch("api.lesson_plan_handler.get_lesson_plan_details.func", return_value=mock_res_str):
        client.cookies.set("session_id", "valid_session_cookie_123")
        response = client.get(f"/api/lesson-plans/{plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["planificacion"]["_id"] == plan_id
