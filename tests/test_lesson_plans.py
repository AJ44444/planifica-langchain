import pytest
import os
import sys
import json
from unittest.mock import patch

# Asegurar que el paquete app esté accesible en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.vector_tool import search_curriculum_vector_db
from core.config import DB


def test_vector_search_mocked_tree():
    """
    2.1 Planificación: Verificar que la búsqueda de vectores requiere id_subarea_relacionada y entrega el árbol del currículum.
    """
    mock_results = [
        {
            "_id": "60d5ec49f1a2c8123456789a",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "nombre_subarea": "Comunicación y Lenguaje L1",
            "tipo_nodo": "competencia",
            "referencia_jerarquica": "1",
            "texto_a_buscar": "Competencia 1: Utiliza la escucha y la habla en forma analítica...",
            "score": 0.92
        }
    ]

    with patch("tools.vector_tool.vector_search_cnb", return_value=mock_results):
        result_json_str = search_curriculum_vector_db.invoke({
            "query": "escucha y habla",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "limit": 5
        })
        result_dict = json.loads(result_json_str)

        assert result_dict.get("status") == "success"
        results = result_dict.get("results", [])
        assert len(results) == 1
        assert results[0]["tipo_nodo"] == "competencia"
        assert results[0]["nombre_subarea"] == "Comunicación y Lenguaje L1"
        assert "referencia_jerarquica" in results[0]
        assert "score" in results[0]


def test_vector_search_live_tree():
    """
    2.1 Planificación: Búsqueda vectorial real en MongoDB (se omite si no hay credenciales en .env).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not DB or not api_key:
        pytest.skip("MONGODB_URI o GOOGLE_API_KEY no configuradas para consulta vectorial en vivo.")

    result_json_str = search_curriculum_vector_db.invoke({
        "query": "competencia comunicación y lenguaje redacción",
        "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
        "limit": 5
    })
    result_dict = json.loads(result_json_str)

    assert result_dict.get("status") == "success"
    results = result_dict.get("results", [])
    assert isinstance(results, list)
