import json
from core.validator import validate_subagent_response


def test_validator_consultas_especializadas_returns_full_text():
    sample_text = "El catálogo de carreras incluye Perito Contador con ID 60d5ecf8b5c9c92b8c8b4567."
    res_str = validate_subagent_response("consultas_especializadas_cnb", sample_text)
    res = json.loads(res_str)
    
    assert res["estado"] == "success"
    assert res["agente"] == "consultas_especializadas_cnb"
    assert res["artefacto_generado"] == sample_text


def test_validator_planning_extracts_only_ids():
    sample_text = "Planificación creada con éxito. ID: 60d5ecf8b5c9c92b8c8b4567."
    res_str = validate_subagent_response("planificador_clases_cnb", sample_text)
    res = json.loads(res_str)
    
    assert res["estado"] == "success"
    assert res["agente"] == "planificador_clases_cnb"
    assert res["artefacto_generado"] == {"id_referencia": "60d5ecf8b5c9c92b8c8b4567"}


def test_validator_instruments_extracts_only_ids():
    sample_text = "Instrumentos guardados 60d5ecf8b5c9c92b8c8b4567 y 60d5ecf8b5c9c92b8c8b4568."
    res_str = validate_subagent_response("instrumentos_evaluacion_cnb", sample_text)
    res = json.loads(res_str)
    
    assert res["estado"] == "success"
    assert res["agente"] == "instrumentos_evaluacion_cnb"
    assert "ids_referencia" in res["artefacto_generado"]
    assert set(res["artefacto_generado"]["ids_referencia"]) == {"60d5ecf8b5c9c92b8c8b4567", "60d5ecf8b5c9c92b8c8b4568"}


def test_validator_multimodal_resources_extracts_only_ids():
    sample_text = "Recurso creado con ID: 60d5ecf8b5c9c92b8c8b4567."
    res_str = validate_subagent_response("recursos_multimodales_cnb", sample_text)
    res = json.loads(res_str)
    
    assert res["estado"] == "success"
    assert res["agente"] == "recursos_multimodales_cnb"
    assert res["artefacto_generado"] == {"id_referencia": "60d5ecf8b5c9c92b8c8b4567"}
