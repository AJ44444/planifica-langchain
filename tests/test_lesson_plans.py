import pytest
import os
import sys
import json
from unittest.mock import patch

# Asegurar que el paquete app esté accesible en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.vector_tool import search_curriculum_vector_db, get_embedding_model
from core.config import get_env_variable


def test_embedding_model_dimensionality():
    """Verifica que el modelo de embeddings esté configurado con el modelo gemini-embedding-2 y dimensión 768."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "mock_key"}):
        emb_model = get_embedding_model()
        assert emb_model.model == "models/gemini-embedding-2"
        assert emb_model.output_dimensionality == 768


def test_vector_search_mocked_tree():
    """
    2.1 Planificación: Verificar que la búsqueda de vectores requiere id_subarea_relacionada y entrega el árbol del currículum.
    """
    res_str = search_curriculum_vector_db.invoke({
        "query": "comunicación",
        "id_subarea_relacionada": "",
        "limit": 5
    })
    res_dict = json.loads(res_str)
    assert res_dict.get("status") == "error"
    assert "obligatorio" in res_dict.get("message", "")

    # Validar formato con ObjectId de 24 caracteres hex
    res_str2 = search_curriculum_vector_db.invoke({
        "query": "comunicación",
        "id_subarea_relacionada": "123_invalid_id",
        "limit": 5
    })
    res_dict2 = json.loads(res_str2)
    assert res_dict2.get("status") == "error"
    assert "ObjectId" in res_dict2.get("message", "")

    mock_results = [
        {
            "_id": "60d5ec49f1a2c8123456789a",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "nombre_subarea": "Comunicación y Lenguaje L1",
            "tipo_nodo": "competencia",
            "referencia_jerarquica": "1",
            "texto_a_buscar": "Competencia 1: Utiliza la escucha y la habla en forma analítica...",
            "score": 0.95
        }
    ]

    with patch("tools.vector_tool.vector_search_cnb", return_value=mock_results):
        result_json_str = search_curriculum_vector_db.invoke({
            "query": "comunicación escucha analítica",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "limit": 5
        })
        result_dict = json.loads(result_json_str)

        assert result_dict.get("status") == "success"
        arbol = result_dict.get("arbol_curricular", [])
        assert isinstance(arbol, list)
        assert len(arbol) == 1


def test_vector_search_live_tree():
    """
    2.1 Planificación: Búsqueda vectorial real en MongoDB (se omite si no hay credenciales en .env).
    """
    mongodb_uri = get_env_variable("MONGODB_URI")
    api_key = get_env_variable("GOOGLE_API_KEY")
    if not mongodb_uri or "test" in mongodb_uri or not api_key or "test" in api_key:
        pytest.skip("MONGODB_URI o GOOGLE_API_KEY no configuradas con credenciales reales para consulta en vivo.")

    result_json_str = search_curriculum_vector_db.invoke({
        "query": "competencia comunicación y lenguaje redacción",
        "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
        "limit": 5
    })
    result_dict = json.loads(result_json_str)

    assert result_dict.get("status") == "success"
    arbol = result_dict.get("arbol_curricular", [])
    assert isinstance(arbol, list)


def test_tree_merging_logic():
    """Verifica la lógica de fusión (merge) cuando dos contenidos pertenecen al mismo indicador."""
    from tools.vector_tool import fetch_subarea_nodes_from_db, build_merged_curriculum_tree
    from unittest.mock import MagicMock

    sample_subarea_doc = {
        "_id": "60d5ec49f1a2c8123456789b",
        "nombre_subarea": "Física General",
        "competencias": [
            {
                "id_competencia": "1",
                "descripcion": "Aplica el conocimiento científico",
                "indicadores_logro": [
                    {
                        "id_indicador": "1.1",
                        "descripcion": "Utiliza conceptos básicos de física",
                        "contenidos": [
                            {"id_contenido": "1.1.1", "descripcion": "Mecánica clásica y vectores"},
                            {"id_contenido": "1.1.2", "descripcion": "Leyes de Newton y movimiento"}
                        ]
                    }
                ]
            }
        ]
    }

    sample_vector_results = [
        {
            "_id": "1",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "tipo_nodo": "contenido",
            "texto_a_buscar": "Mecánica clásica y vectores"
        },
        {
            "_id": "2",
            "id_subarea_relacionada": "60d5ec49f1a2c8123456789b",
            "tipo_nodo": "contenido",
            "texto_a_buscar": "Leyes de Newton y movimiento"
        }
    ]

    mock_db = MagicMock()
    mock_db["cnb_subareas"].find_one.return_value = sample_subarea_doc

    elements = fetch_subarea_nodes_from_db(sample_vector_results, db=mock_db)
    assert len(elements) == 2
    assert elements[0]["competencia"]["descripcion"] == "Aplica el conocimiento científico"
    assert elements[0]["indicador"]["descripcion"] == "Utiliza conceptos básicos de física"
    assert elements[0]["contenido"]["descripcion"] == "Mecánica clásica y vectores"

    tree = build_merged_curriculum_tree(elements)
    assert len(tree) == 1
    assert tree[0]["id_competencia"] == "1"
    assert tree[0]["competencia"] == "Aplica el conocimiento científico"
    assert len(tree[0]["indicadores"]) == 1
    assert tree[0]["indicadores"][0]["id_indicador"] == "1.1"
    assert len(tree[0]["indicadores"][0]["contenidos"]) == 2
    assert tree[0]["indicadores"][0]["contenidos"][0]["descripcion"] == "Mecánica clásica y vectores"
    assert tree[0]["indicadores"][0]["contenidos"][1]["descripcion"] == "Leyes de Newton y movimiento"
