import pytest
import os
import sys
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from core.tool_inputs import (
    SaveLessonPlanInput,
    SaveAssessmentInstrumentInput,
    SaveMultimodalResourceInput,
    SaveCurricularStructureInput,
    GetPlanificationByIdInput,
    UpdateLessonPlanInput,
)
from tools.persistence_tool import (
    save_lesson_plan,
    save_assessment_instrument,
    save_multimodal_resource,
    get_planification_by_id,
    update_lesson_plan,
)


def test_save_lesson_plan_tool_schema_validation():
    """Verifica que save_lesson_plan valide correctamente su entrada utilizando el schema Pydantic."""
    assert save_lesson_plan.args_schema == SaveLessonPlanInput

    sample_input = {
        "metadatos": {
            "carrera": "Ciclo Básico",
            "subarea_curricular": "Matemáticas 1",
            "estado": "finalizado"
        },
        "encabezado": {
            "centro_educativo": "INEB Central",
            "lugar": "Guatemala",
            "grado": "Primero Básico",
            "seccion": "A",
            "nombre_docente": "Juan Pérez",
            "duracion": 1
        },
        "desarrollo_curricular": [
            {
                "id_fila": 1,
                "competencia": "Resuelve problemas matemáticos",
                "indicadores_logro": [
                    {
                        "indicador": "Aplica la suma y resta",
                        "contenidos": ["Suma", "Resta"]
                    }
                ],
                "actividades_aprendizaje": [
                    {
                        "id_actividad": "60d5ec49f1a2c8123456789a",
                        "fase": "inicio",
                        "descripcion": "Resolver acertijo numérico"
                    }
                ]
            }
        ],
        "id_usuario": "60d5ec49f1a2c81234567890"
    }

    mock_db = MagicMock()
    mock_db["planificaciones_generadas"].insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567899")

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_str = save_lesson_plan.invoke(sample_input)
        res = json.loads(res_str)
        assert res.get("status") == "success"
        assert res.get("id_planificacion") == "60d5ec49f1a2c81234567899"


def test_save_assessment_instrument_tool_schema_validation():
    """Verifica que save_assessment_instrument valide su entrada mediante SaveAssessmentInstrumentInput."""
    assert save_assessment_instrument.args_schema == SaveAssessmentInstrumentInput

    sample_input = {
        "id_planificacion": "60d5ec49f1a2c81234567899",
        "id_fila_curricular": 1,
        "id_actividad": "60d5ec49f1a2c8123456789a",
        "tipo": "rubrica",
        "titulo": "Rúbrica de Resolución de Problemas",
        "instrumento_generado": {
            "escala": ["Excelente", "Bueno", "Debe mejorar"],
            "criterios": [
                {
                    "nombre": "Comprensión del problema",
                    "definiciones": ["Identifica datos correctamente", "Identifica datos parcialmente", "No identifica datos"]
                }
            ]
        }
    }

    mock_db = MagicMock()
    mock_db["instrumentos_evaluacion"].insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567898")

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_str = save_assessment_instrument.invoke(sample_input)
        res = json.loads(res_str)
        assert res.get("status") == "success"
        assert res.get("id_instrumento") == "60d5ec49f1a2c81234567898"


def test_save_multimodal_resource_tool_schema_validation():
    """Verifica que save_multimodal_resource valide su entrada mediante SaveMultimodalResourceInput."""
    assert save_multimodal_resource.args_schema == SaveMultimodalResourceInput

    sample_input = {
        "id_planificacion": "60d5ec49f1a2c81234567899",
        "id_fila_curricular": 1,
        "id_actividad": "60d5ec49f1a2c8123456789a",
        "tipo": "video",
        "titulo": "Video explicativo de álgebra",
        "url": "https://www.youtube.com/watch?v=example"
    }

    mock_db = MagicMock()
    mock_db["recursos_multimodales"].insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567897")

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_str = save_multimodal_resource.invoke(sample_input)
        res = json.loads(res_str)
        assert res.get("status") == "success"
        assert res.get("id_recurso") == "60d5ec49f1a2c81234567897"
