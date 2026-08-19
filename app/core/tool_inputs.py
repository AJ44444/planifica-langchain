from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from core.response_formats import (
    Subarea,
    EncabezadoPlan,
    FilaCurricularPlan,
    InstrumentoGeneradoDetail,
)


class MetadatosPlanInput(BaseModel):
    """Metadatos de la planificación docente."""
    carrera: str = Field(..., description="Nombre de la carrera académica (ej. 'Ciclo Básico').")
    subarea_curricular: str = Field(..., description="Nombre del curso o subárea (ej. 'Matemáticas 1').")
    estado: Optional[str] = Field(default="finalizado", description="Estado del registro del plan.")


class SaveCurricularStructureInput(BaseModel):
    """Input para guardar la estructura curricular del CNB."""
    nombre_carrera: str = Field(..., description="Nombre de la carrera académica.")
    nombre_area: str = Field(..., description="Nombre del área curricular principal.")
    competencias_area: List[str] = Field(default_factory=list, description="Competencias generales del área.")
    actividades_sugeridas: List[str] = Field(default_factory=list, description="Actividades orientadoras sugeridas del área.")
    criterios_evaluacion_sugeridos: List[str] = Field(default_factory=list, description="Criterios globales de evaluación del área.")
    subareas: List[Subarea] = Field(default_factory=list, description="Subáreas asociadas con competencias, indicadores y contenidos.")


class SaveLessonPlanInput(BaseModel):
    """Input estructurado para crear una nueva planificación docente."""
    metadatos: MetadatosPlanInput = Field(..., description="Metadatos como carrera, subárea curricular y estado.")
    encabezado: EncabezadoPlan = Field(..., description="Información administrativa del plan (centro_educativo, lugar, grado, seccion, duracion, cantidad_periodos, duracion_periodos).")
    desarrollo_curricular: List[FilaCurricularPlan] = Field(..., description="Lista de filas de desarrollo pedagógico y actividades de aprendizaje.")
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB (24 caracteres) del docente autenticado.")


class GetPlanificationByIdInput(BaseModel):
    """Input para consultar una planificación por su ID."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación.")
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente para validación de propiedad.")


class UpdateLessonPlanInput(BaseModel):
    """Input para actualizar campos específicos de una planificación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres) de la planificación a actualizar.")
    update_data: Dict[str, Any] = Field(..., description="Diccionario estructurado con los campos a actualizar mediante $set.")
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")


class DeleteLessonPlanInput(BaseModel):
    """Input para eliminar una planificación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres) de la planificación a eliminar.")
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")
    confirm: bool = Field(default=True, description="Confirmación explícita para eliminar el registro.")


class SaveAssessmentInstrumentInput(BaseModel):
    """Input para guardar un instrumento de evaluación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres) de la planificación vinculada.")
    id_fila: int = Field(default=1, description="Fila curricular evaluada.")
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres) de la actividad evaluada.")
    tipo: Literal["lista_cotejo", "rubrica", "escala_rango"] = Field(..., description="Tipo de instrumento de evaluación.")
    titulo: str = Field(..., description="Título único del instrumento de evaluación.")
    instrumento_generado: InstrumentoGeneradoDetail = Field(..., description="Detalle del instrumento con escala y criterios.")


class GetAssessmentInstrumentByIdInput(BaseModel):
    """Input para consultar un instrumento por su ID."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres) del instrumento de evaluación.")


class UpdateAssessmentInstrumentInput(BaseModel):
    """Input para actualizar un instrumento de evaluación."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres) del instrumento a actualizar.")
    update_data: Dict[str, Any] = Field(..., description="Diccionario estructurado con los campos a actualizar mediante $set.")


class DeleteAssessmentInstrumentInput(BaseModel):
    """Input para eliminar un instrumento de evaluación."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres) del instrumento a eliminar.")
    confirm: bool = Field(default=True, description="Confirmación explícita para eliminar.")


class SaveMultimodalResourceInput(BaseModel):
    """Input para guardar un recurso multimodal."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres) de la planificación vinculada.")
    id_fila: int = Field(default=1, description="Fila curricular asociada.")
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres) de la actividad asociada.")
    tipo: Literal["video", "imagen", "audio", "documento", "sitio_web"] = Field(..., description="Tipo de recurso multimodal.")
    titulo: str = Field(..., description="Título descriptivo del recurso.")
    url: str = Field(..., description="Enlace URL directo verídico obtenido del buscador web.")


class GetMultimodalResourceByIdInput(BaseModel):
    """Input para consultar un recurso multimodal por su ID."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres) del recurso multimodal.")


class UpdateMultimodalResourceInput(BaseModel):
    """Input para actualizar un recurso multimodal."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres) del recurso a actualizar.")
    update_data: Dict[str, Any] = Field(..., description="Diccionario estructurado con los campos a actualizar mediante $set.")


class DeleteMultimodalResourceInput(BaseModel):
    """Input para eliminar un recurso multimodal."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres) del recurso a eliminar.")
    confirm: bool = Field(default=True, description="Confirmación explícita para eliminar.")


class GetTopFrequentCoursesInput(BaseModel):
    """Input para consultar los cursos más frecuentes del docente."""
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")
    limit: int = Field(default=4, description="Límite máximo de registros a retornar.")


class GetRecentLessonPlansInput(BaseModel):
    """Input para consultar las últimas planificaciones creadas."""
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")
    limit: int = Field(default=3, description="Límite máximo de planificaciones recientes.")


class GetLatestPlanInstrumentsAndResourcesInput(BaseModel):
    """Input para consultar los últimos instrumentos y recursos del docente."""
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")


class GetPaginatedLessonPlansInput(BaseModel):
    """Input para consultar el historial paginado de planificaciones."""
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")
    page: int = Field(default=1, description="Número de página a consultar.")
    limit: int = Field(default=10, description="Cantidad de registros por página.")


class GetFullLessonPlanDetailsInput(BaseModel):
    """Input para consultar el detalle completo de una planificación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres) de la planificación.")
    id_usuario: Optional[str] = Field(default="", description="ID de MongoDB del docente autenticado.")


class GetCNBAreasByCareerInput(BaseModel):
    """Input para consultar la lista paginada de áreas curriculares pertenecientes a una carrera."""
    carrera: str = Field(..., description="Nombre de la carrera académica del CNB.")
    page: int = Field(default=1, description="Número de página a consultar.")
    limit: int = Field(default=10, description="Cantidad de registros por página.")


GetCNBAreasByCareersInput = GetCNBAreasByCareerInput


class GetCNBSubareasByAreaIdInput(BaseModel):
    """Input para consultar la lista paginada de subáreas pertenecientes a un área curricular."""
    id_area: str = Field(..., description="ID de MongoDB (24 caracteres hex) del área curricular.")
    page: int = Field(default=1, description="Número de página a consultar.")
    limit: int = Field(default=10, description="Cantidad de registros por página.")


class SearchCurriculumVectorDBInput(BaseModel):
    """Input para realizar una búsqueda vectorial semántica en el CNB."""
    query: str = Field(..., description="Tema, competencia o contenido pedagógico a buscar.")
    id_subarea_relacionada: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea curricular. Obligatorio.")
    limit: int = Field(default=5, description="Cantidad máxima de resultados a retornar.")


class GenerateSubareaVectorEmbeddingsInput(BaseModel):
    """Input para generar embeddings de una subárea."""
    id_subarea_relacionada: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea a vectorizar.")
