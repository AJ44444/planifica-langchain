"""
Módulo core de configuración, modelo de lenguaje (LLM), colecciones e interfaces de datos Pydantic.
"""

from .config import DEEPSEEK, DB, DB_NAME, SERPER, GOOGLE_CLIENT_ID
from .llm import llm
from .collections import (
    AREAS,
    SUBAREAS,
    VECTORES,
    PLANIFICACION,
    EVALUACION,
    RECURSOS,
    USUARIOS,
    CHECKPOINTS,
    CHECKPOINT_WRITES,
)
from .response_formats import (
    EstructuraCurricular,
    ProcessPDFResponse,
    PlanificacionClase,
    SchoolLessonPlanResponse,
    InstrumentoEvaluacion,
    SchoolAssessmentInstrumentResponse,
    RecursoMultimodal,
    SchoolMultimodalResourceResponse,
)

__all__ = [
    "DEEPSEEK",
    "DB",
    "DB_NAME",
    "SERPER",
    "GOOGLE_CLIENT_ID",
    "llm",
    "AREAS",
    "SUBAREAS",
    "VECTORES",
    "PLANIFICACION",
    "EVALUACION",
    "RECURSOS",
    "USUARIOS",
    "CHECKPOINTS",
    "CHECKPOINT_WRITES",
    "EstructuraCurricular",
    "ProcessPDFResponse",
    "PlanificacionClase",
    "SchoolLessonPlanResponse",
    "InstrumentoEvaluacion",
    "SchoolAssessmentInstrumentResponse",
    "RecursoMultimodal",
    "SchoolMultimodalResourceResponse",
]
