import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Asegurar que el paquete app esté accesible en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.web_search_tool import serper_web_search
from core.config import SERPER


def test_serper_web_search_mocked_results():
    """
    3.1 Recursos: Verificar que la búsqueda web (SERPER) entregue resultados estructurados.
    """
    mock_raw_results = {
        "organic": [
            {
                "title": "Recursos Didácticos de Física - CNB Guatemala",
                "link": "https://cnbguatemala.org/recursos/fisica",
                "snippet": "Guías experimentales de física para secundaria del CNB."
            }
        ]
    }

    mock_wrapper_instance = MagicMock()
    mock_wrapper_instance.results.return_value = mock_raw_results

    with patch("tools.web_search_tool.SERPER", "mock_key_for_unit_test"), \
         patch("tools.web_search_tool.get_serper_wrapper", return_value=mock_wrapper_instance):

        res_json = serper_web_search.invoke({
            "query": "experimentos física secundaria CNB",
            "search_type": "search",
            "num_results": 1
        })
        res_data = json.loads(res_json)

        assert res_data.get("status") == "success"
        results = res_data.get("results", [])
        assert len(results) == 1
        assert results[0]["title"] == "Recursos Didácticos de Física - CNB Guatemala"
        assert results[0]["link"] == "https://cnbguatemala.org/recursos/fisica"
        assert results[0]["tipo"] == "sitio_web"


def test_serper_web_search_live_results():
    """
    3.1 Recursos: Búsqueda web real con la API de SERPER (se omite si no hay SERPER_API en .env).
    """
    if not SERPER:
        pytest.skip("SERPER_API no configurada en .env para prueba de búsqueda en vivo.")

    res_json = serper_web_search.invoke({
        "query": "experimentos de física secundaria CNB Guatemala",
        "search_type": "search",
        "num_results": 3
    })
    res_data = json.loads(res_json)

    assert res_data.get("status") == "success"
    results = res_data.get("results", [])
    assert isinstance(results, list)
    assert len(results) > 0
