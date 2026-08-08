"""
Módulo core de configuración, modelo de lenguaje (LLM), colecciones e interfaces de datos Pydantic.
"""

from .config import (
    DEEPSEEK,
    GOOGLE,
    MONGODB_URI,
    DB_NAME,
    SERPER,
    GOOGLE_CLIENT_ID,
    POSTGRES_URI,
    REDIS_URI,
    LANGGRAPH_AUTH,
    LANGSERVE_GRAPHS,
)
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
    "MONGODB_URI",
    "DB_NAME",
    "SERPER",
    "GOOGLE_CLIENT_ID",
    "POSTGRES_URI",
    "REDIS_URI",
    "LANGGRAPH_AUTH",
    "LANGSERVE_GRAPHS",
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
