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
    UpdateLessonPlanInput,
    UpdateAssessmentInstrumentInput,
    UpdateMultimodalResourceInput,
)
from tools.persistence_tool import (
    save_lesson_plan,
    save_assessment_instrument,
    save_multimodal_resource,
    update_lesson_plan,
    update_assessment_instrument,
    update_multimodal_resource,
    get_learning_activity_by_id,
)


def test_save_lesson_plan_tool_schema_validation():
    """Verifies that save_lesson_plan correctly validates input using Pydantic schema."""
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
            "duracion": "1 día",
            "cantidad_periodos": 1,
            "duracion_periodos": 40
        },
        "desarrollo_curricular": [
            {
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
    """Verifies that save_assessment_instrument validates input via SaveAssessmentInstrumentInput."""
    assert save_assessment_instrument.args_schema == SaveAssessmentInstrumentInput

    sample_input = {
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
    """Verifies that save_multimodal_resource validates input via SaveMultimodalResourceInput."""
    assert save_multimodal_resource.args_schema == SaveMultimodalResourceInput

    sample_input = {
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


def test_get_learning_activity_by_id():
    """Verifies destructured retrieval of a learning activity by ID in pipeline."""
    mock_db = MagicMock()
    mock_db["planificaciones_generadas"].aggregate.return_value = [
        {
            "id_actividad": ObjectId("60d5ec49f1a2c8123456789a"),
            "fase": "inicio",
            "descripcion": "Resolver acertijo numérico"
        }
    ]

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_str = get_learning_activity_by_id.invoke({"id_actividad": "60d5ec49f1a2c8123456789a"})
        res = json.loads(res_str)
        assert res.get("status") == "success"
        assert res.get("actividad", {}).get("id_actividad") == "60d5ec49f1a2c8123456789a"


def test_cnb_catalog_query_tools():
    """Verifies that CNB query tools have correct projections and signatures."""
    from tools.persistence_tool import (
        get_cnb_careers_list,
        get_cnb_areas_by_career,
        get_cnb_subareas_by_area_id,
    )

    mock_areas_coll = MagicMock()
    mock_areas_coll.distinct.return_value = ["Ciclo Básico", "Bachillerato en Ciencias y Letras"]
    mock_areas_coll.count_documents.return_value = 1
    mock_area_doc = {"_id": ObjectId("60d5ec49f1a2c81234567811"), "nombre_area": "Matemáticas"}
    mock_areas_coll.find.return_value.skip.return_value.limit.return_value = [mock_area_doc]

    mock_subareas_coll = MagicMock()
    mock_subareas_coll.count_documents.return_value = 1
    mock_subarea_doc = {"_id": ObjectId("60d5ec49f1a2c81234567822"), "nombre_subarea": "Matemáticas 1", "competencias": []}
    mock_subareas_coll.find.return_value.skip.return_value.limit.return_value = [mock_subarea_doc]

    mock_db = {
        "cnb_areas": mock_areas_coll,
        "cnb_subareas": mock_subareas_coll
    }

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_careers = json.loads(get_cnb_careers_list.invoke({}))
        assert res_careers["status"] == "success"
        assert res_careers["carreras"] == ["Ciclo Básico", "Bachillerato en Ciencias y Letras"]

        res_areas = json.loads(get_cnb_areas_by_career.invoke({"carrera": "Ciclo Básico", "page": 1, "limit": 10}))
        assert res_areas["status"] == "success"
        assert res_areas["areas"] == [{"id_area": "60d5ec49f1a2c81234567811", "nombre_area": "Matemáticas"}]

        res_subareas = json.loads(get_cnb_subareas_by_area_id.invoke({"id_area": "60d5ec49f1a2c81234567811", "page": 1, "limit": 10}))
        assert res_subareas["status"] == "success"
        assert res_subareas["subareas"] == [{"id_subarea": "60d5ec49f1a2c81234567822", "nombre_subarea": "Matemáticas 1"}]


def test_update_tools_schema_validation():
    """Verifies that update tools have assigned Pydantic args_schemas."""
    assert update_lesson_plan.args_schema == UpdateLessonPlanInput
    assert update_assessment_instrument.args_schema == UpdateAssessmentInstrumentInput
    assert update_multimodal_resource.args_schema == UpdateMultimodalResourceInput


def test_save_curricular_structure_with_pydantic_objects():
    """Verifies save_curricular_structure with Pydantic SaveCurricularStructureInput objects."""
    from tools.persistence_tool import save_curricular_structure
    from core.tool_inputs import (
        SaveCurricularStructureInput,
        Subarea,
        CompetenciaEspecifica,
        IndicadorLogro,
        Contenido,
    )

    pydantic_input = SaveCurricularStructureInput(
        nombre_carrera="Bachillerato en Ciencias y Letras con Orientación en Computación",
        nombre_area="Matemáticas",
        actividades_sugeridas=["Resolución de problemas de álgebra"],
        criterios_evaluacion_sugeridos=["Aplica fórmulas algebraicas correctamente"],
        subareas=[
            Subarea(
                nombre_subarea="Matemáticas Cuarto Grado",
                competencias=[
                    CompetenciaEspecifica(
                        id_competencia="1",
                        descripcion="Aplica propiedades matemáticas",
                        indicadores_logro=[
                            IndicadorLogro(
                                id_indicador="1.1",
                                descripcion="Resuelve operaciones complejas",
                                contenidos=[
                                    Contenido(id_contenido="1.1.1", descripcion="Ecuaciones de segundo grado")
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )

    mock_areas = MagicMock()
    mock_areas.insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567810")
    mock_subareas = MagicMock()
    mock_subareas.insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567820")
    mock_vectores = MagicMock()
    mock_vectores.insert_one.return_value.inserted_id = ObjectId("60d5ec49f1a2c81234567830")

    mock_db = {
        "cnb_areas": mock_areas,
        "cnb_subareas": mock_subareas,
        "cnb_vectores": mock_vectores
    }

    with patch("tools.persistence_tool.get_db", return_value=mock_db):
        res_str = save_curricular_structure(
            nombre_carrera=pydantic_input.nombre_carrera,
            nombre_area=pydantic_input.nombre_area,
            actividades_sugeridas=pydantic_input.actividades_sugeridas,
            criterios_evaluacion_sugeridos=pydantic_input.criterios_evaluacion_sugeridos,
            subareas=pydantic_input.subareas
        )

        res = json.loads(res_str)
        assert res["status"] == "success"
        assert res["id_area"] == "60d5ec49f1a2c81234567810"
        assert len(res["subareas_insertadas"]) == 1
        assert res["subareas_insertadas"][0]["nombre_subarea"] == "Matemáticas Cuarto Grado"
        assert res["subareas_insertadas"][0]["id_subarea"] == "60d5ec49f1a2c81234567820"
        # 1 competencia + 1 indicador + 1 contenido = 3 vector nodes
        assert res["nodos_vectoriales_creados"] == 3

