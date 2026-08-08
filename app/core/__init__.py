"""
Módulo core de configuración, modelo de lenguaje (LLM), colecciones e interfaces de datos Pydantic.
"""

from .config import DEEPSEEK, GOOGLE, DB, DB_NAME, SERPER, GOOGLE_CLIENT_ID
from .llm import llm
from .collections import (
    AREAS,
    SUBAREAS,
    VECTORES,
    PLANIFICACION,
    EVALUACION,
    RECURSOS,
    USUARIOS,
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
    "GOOGLE",
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
    "EstructuraCurricular",
    "ProcessPDFResponse",
    "PlanificacionClase",
    "SchoolLessonPlanResponse",
    "InstrumentoEvaluacion",
    "SchoolAssessmentInstrumentResponse",
    "RecursoMultimodal",
    "SchoolMultimodalResourceResponse",
]
