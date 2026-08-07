from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel


# ==============================================================================
# 1. FORMATO DE RESPUESTA: PROCESADOR DE PDF DEL CNB
# ==============================================================================

class Contenido(BaseModel):
    id_contenido: str
    descripcion: str


class IndicadorLogro(BaseModel):
    id_indicador: str
    descripcion: str
    contenidos: List[Contenido]


class CompetenciaEspecifica(BaseModel):
    id_competencia: str
    descripcion: str
    indicadores_logro: List[IndicadorLogro]


class Subarea(BaseModel):
    nombre_subarea: str
    competencias: List[CompetenciaEspecifica]


class EstructuraCurricular(BaseModel):
    nombre_carrera: str
    nombre_area: str
    competencias_area: List[str]
    actividades_sugeridas: List[str]
    criterios_evaluacion_sugeridos: List[str]
    subareas: List[Subarea]


# Alias para compatibilidad
ProcessPDFResponse = EstructuraCurricular


# ==============================================================================
# 2. FORMATO DE RESPUESTA: PLANIFICADOR DE CLASES DE PLANIFICA
# ==============================================================================

class EncabezadoPlan(BaseModel):
    centro_educativo: str
    lugar: str
    grado: str
    seccion: str
    nombre_docente: str
    duracion: int


class ActividadAprendizaje(BaseModel):
    id_actividad: int
    fase: Literal["inicio", "desarrollo", "cierre"]
    descripcion: str


class IndicadorPlanItem(BaseModel):
    indicador: str
    contenidos: List[str]


class FilaCurricularPlan(BaseModel):
    id_fila: int
    competencia: str
    indicadores_logro: List[IndicadorPlanItem]
    actividades_aprendizaje: List[ActividadAprendizaje]


class PlanificacionClase(BaseModel):
    encabezado: EncabezadoPlan
    desarrollo_curricular: List[FilaCurricularPlan]


# Alias para compatibilidad
SchoolLessonPlanResponse = PlanificacionClase


# ==============================================================================
# 3. FORMATO DE RESPUESTA: INSTRUMENTOS DE EVALUACIÓN
# ==============================================================================

class CriterioEvaluacion(BaseModel):
    id_criterio: int
    nombre: str
    descripcion: str
    ponderacion: Optional[float] = None


class InstrumentoGeneradoDetail(BaseModel):
    criterios: List[CriterioEvaluacion]
    escala_calificacion: List[str]
    instrucciones: str = ""


class InstrumentoEvaluacion(BaseModel):
    id_planificacion: str
    id_fila_curricular: int = 1
    id_actividad: int = 1
    tipo: Literal["lista_cotejo", "rubrica", "escala_rango"]
    titulo: str
    instrumento_generado: InstrumentoGeneradoDetail


# Alias para compatibilidad
SchoolAssessmentInstrumentResponse = InstrumentoEvaluacion


# ==============================================================================
# 4. FORMATO DE RESPUESTA: RECURSOS MULTIMODALES
# ==============================================================================

class RecursoMultimodal(BaseModel):
    id_planificacion: str
    id_fila_curricular: int = 1
    id_actividad: int = 1
    tipo: Literal["video", "imagen", "audio", "documento", "sitio_web"]
    titulo: str
    url: str
    busqueda_query: str
    descripcion_recurso: str


# Alias para compatibilidad
SchoolMultimodalResourceResponse = RecursoMultimodal
