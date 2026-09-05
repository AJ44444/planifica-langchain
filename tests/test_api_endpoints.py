import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from server import app
from auth.auth_handler import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def test_get_paginated_lesson_plans_endpoint_unauthenticated(client):
    """Verifica que /api/lesson-plans rechace peticiones no autenticadas con 401."""
    response = client.get("/api/lesson-plans")
    assert response.status_code == 401
    assert "Acceso Denegado" in response.json()["detail"]


def test_get_paginated_lesson_plans_endpoint_success(client):
    """Verifica que /api/lesson-plans retorne el historial paginado del usuario autenticado."""
    user_id = "60d5ec49f1a2c8123456789a"
    token = create_access_token(user_id=user_id, email="docente@escuela.edu.gt")

    mock_res_str = json.dumps({
        "status": "success",
        "total_registros": 1,
        "total_paginas": 1,
        "pagina_actual": 1,
        "registros_por_pagina": 10,
        "planificaciones": [{"_id": "60d5ec49f1a2c8123456789b"}]
    })

    with patch("api.lesson_plan_handler.get_paginated_lesson_plans.func", return_value=mock_res_str):
        client.cookies.set("access_token", token)
        response = client.get("/api/lesson-plans?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["planificaciones"]) == 1


def test_get_lesson_plan_details_endpoint_unauthenticated(client):
    """Verifica que /api/lesson-plans/{id_planificacion} rechace peticiones no autenticadas con 401."""
    response = client.get("/api/lesson-plans/60d5ec49f1a2c8123456789b")
    assert response.status_code == 401
    assert "Acceso Denegado" in response.json()["detail"]


def test_get_lesson_plan_details_endpoint_success(client):
    """Verifica que /api/lesson-plans/{id_planificacion} retorne el detalle completo."""
    user_id = "60d5ec49f1a2c8123456789a"
    plan_id = "60d5ec49f1a2c8123456789b"
    token = create_access_token(user_id=user_id, email="docente@escuela.edu.gt")

    mock_res_str = json.dumps({
        "status": "success",
        "planificacion": {"_id": plan_id},
        "instrumentos_evaluacion": [],
        "recursos_multimodales": []
    })

    with patch("api.lesson_plan_handler.get_lesson_plan_details.func", return_value=mock_res_str):
        client.cookies.set("access_token", token)
        response = client.get(f"/api/lesson-plans/{plan_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["planificacion"]["_id"] == plan_id
