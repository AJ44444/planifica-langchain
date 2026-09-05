import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Ensure app package is accessible in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from tools.web_search_tool import serper_web_search
from core.config import get_env_variable


def test_serper_web_search_mocked_results():
    """
    Verifies that web search (SERPER) returns structured results.
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

    with patch.dict(os.environ, {"SERPER_API_KEY": "mock_key_for_unit_test"}), \
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
    Real web search with SERPER API (skipped if SERPER_API_KEY absent).
    """
    serper = os.getenv("SERPER_API_KEY")
    if not serper or "test" in serper:
        pytest.skip("SERPER_API_KEY not configured with live credentials in .env for live test.")

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
