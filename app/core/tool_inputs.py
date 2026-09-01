import re
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field


# ==============================================================================
# 1. MODELOS DE DATOS DE PLANIFICACIÓN E ESTRUCTURAS CURRICULARES DE SUBÁREA
# ==============================================================================

class Contenido(BaseModel):
    """Modelo de contenido temático."""
    id_contenido: Optional[str] = Field(default="", description="Identificador del contenido.")
    descripcion: str = Field(..., description="Descripción del contenido.")


class IndicadorLogro(BaseModel):
    """Modelo de indicador de logro."""
    id_indicador: Optional[str] = Field(default="", description="Identificador del indicador de logro.")
    descripcion: str = Field(..., description="Descripción del indicador de logro.")
    contenidos: List[Contenido] = Field(default_factory=list, description="Lista de contenidos asociados.")


class CompetenciaEspecifica(BaseModel):
    """Modelo de competencia específica."""
    id_competencia: Optional[str] = Field(default="", description="Identificador de la competencia.")
    descripcion: str = Field(..., description="Descripción de la competencia.")
    indicadores_logro: List[IndicadorLogro] = Field(default_factory=list, description="Lista de indicadores de logro.")


class Subarea(BaseModel):
    """Modelo de subárea curricular."""
    nombre_subarea: str = Field(..., description="Nombre de la subárea curricular.")
    competencias: List[CompetenciaEspecifica] = Field(default_factory=list, description="Lista de competencias de la subárea.")


class EncabezadoPlan(BaseModel):
    """Encabezado informativo de una planificación docente."""
    centro_educativo: str = Field(..., description="Nombre del centro educativo.")
    lugar: str = Field(..., description="Ubicación geográfica (municipio/departamento).")
    grado: str = Field(..., description="Grado académico (ej. '4to', 'Primero Básico').")
    seccion: str = Field(..., description="Sección académica (ej. 'A').")
    duracion: str = Field(..., description="Duración (ej. '1 semana', '1 bimestre').")
    cantidad_periodos: int = Field(..., description="Cantidad total de periodos de clase.")
    duracion_periodos: int = Field(..., description="Duración de cada periodo en minutos.")


class ActividadAprendizaje(BaseModel):
    """Actividad de aprendizaje pedagógica."""
    id_actividad: Optional[str] = Field(default=None, description="ID único de la actividad.")
    fase: Literal["inicio", "desarrollo", "cierre"] = Field(..., description="Fase pedagógica de la actividad.")
    descripcion: str = Field(..., description="Descripción impersonal con verbo en infinitivo.")


class IndicadorPlanItem(BaseModel):
    """Item de indicador con contenidos asociados."""
    indicador: str = Field(..., description="Descripción del indicador de logro.")
    contenidos: List[str] = Field(..., description="Lista de contenidos asociados.")


class FilaCurricularPlan(BaseModel):
    """Fila aplanada de desarrollo curricular."""
    id_fila: int = Field(..., description="ID ordinal de la fila.")
    competencia: str = Field(..., description="Descripción de la competencia.")
    indicadores_logro: List[IndicadorPlanItem] = Field(..., description="Lista de indicadores de logro.")
    actividades_aprendizaje: List[ActividadAprendizaje] = Field(..., description="Lista de actividades de aprendizaje.")


class PlanificacionClase(BaseModel):
    """Estructura completa de una planificación docente."""
    encabezado: EncabezadoPlan
    desarrollo_curricular: List[FilaCurricularPlan]


class CriterioEvaluacion(BaseModel):
    """Criterio de evaluación de un instrumento."""
    nombre: str = Field(..., description="Nombre del criterio.")
    definiciones: List[str] = Field(..., description="Definiciones o niveles por desempeño.")


class InstrumentoGeneradoDetail(BaseModel):
    """Detalle técnico del instrumento generado."""
    escala: List[str] = Field(..., description="Escala de desempeño (ej. ['Excelente', 'Bueno']).")
    criterios: List[CriterioEvaluacion] = Field(..., description="Lista de criterios.")


class CurricularAreaModel(BaseModel):
    """Modelo para representar un Área Curricular."""
    id_area: str = Field(..., description="Identificador único numérico del área curricular.")
    nombre_area: str = Field(..., description="Nombre del área curricular.")
    competencias_area: Optional[List[str]] = Field(default_factory=list, description="Lista de competencias del área.")
    actividades_sugeridas: Optional[List[str]] = Field(default_factory=list, description="Lista de actividades sugeridas.")
    criterios_evaluacion: Optional[List[str]] = Field(default_factory=list, description="Lista de criterios de evaluación.")
    subareas: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Lista de subáreas pertenecientes al área.")


class MetadatosPlanInput(BaseModel):
    """Input para metadatos opcionales de una planificación."""
    subarea_curricular: Optional[str] = Field(default="", description="Nombre de la subárea curricular.")
    estado: Optional[str] = Field(default="borrador", description="Estado del documento: 'borrador', 'publicado', 'archivado'.")


# ==============================================================================
# 2. ESQUEMAS DE ENTRADA TIPADOS PARA TODAS LAS HERRAMIENTAS (args_schema)
# ==============================================================================

class ParseCurricularAreasInput(BaseModel):
    """Input estrictamente tipado para la herramienta de parseo de PDF."""
    pdf_base64: str = Field(..., description="Cadena del documento PDF codificada exclusivamente en Base64.")


class SerperWebSearchInput(BaseModel):
    """Input estrictamente tipado para búsquedas en la web mediante SERPER."""
    query: str = Field(..., description="Consulta o palabras clave de búsqueda.")
    search_type: str = Field(default="search", description="Tipo de búsqueda: 'search' (web), 'videos', 'images'.")
    num_results: int = Field(default=5, description="Cantidad máxima de resultados a retornar.")


class SaveCurricularStructureInput(BaseModel):
    """Input estrictamente tipado para guardar la estructura curricular parseada del CNB."""
    nombre_carrera: str = Field(..., description="Nombre oficial de la carrera (ej. Bachillerato en Computación).")
    nombre_area: str = Field(..., description="Nombre del área curricular.")
    competencias_area: List[str] = Field(default_factory=list, description="Lista de competencias del área.")
    actividades_sugeridas: List[str] = Field(default_factory=list, description="Lista de actividades sugeridas del área.")
    criterios_evaluacion_sugeridos: List[str] = Field(default_factory=list, description="Lista de criterios de evaluación sugeridos.")
    subareas: List[Subarea] = Field(..., description="Lista de subáreas pertenecientes al área con sus competencias e indicadores.")


class SaveLessonPlanInput(BaseModel):
    """Input estrictamente tipado para guardar una planificación docente en MongoDB."""
    metadatos: Dict[str, Any] = Field(..., description="Metadatos opcionales como estado, subárea curricular, etc.")
    encabezado: Dict[str, Any] = Field(..., description="Datos generales de encabezado del plan.")
    desarrollo_curricular: List[Dict[str, Any]] = Field(..., description="Filas aplanadas de desarrollo curricular.")
    id_usuario: Optional[str] = Field(default="", description="ID del usuario opcional.")


class GetSubareaTreeInput(BaseModel):
    """Input estrictamente tipado para consultar el árbol de una subárea."""
    id_subarea: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea curricular.")


class GetPlanificationByIdInput(BaseModel):
    """Input estrictamente tipado para consultar una planificación por ID."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación.")


class UpdateLessonPlanInput(BaseModel):
    """Input estrictamente tipado para actualizar una planificación docente."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación a actualizar.")
    encabezado: Optional[Dict[str, Any]] = Field(default=None, description="Datos de encabezado actualizados.")
    desarrollo_curricular: Optional[List[Dict[str, Any]]] = Field(default=None, description="Desarrollo curricular actualizado.")
    metadatos: Optional[Dict[str, Any]] = Field(default=None, description="Metadatos actualizados.")


class DeleteLessonPlanInput(BaseModel):
    """Input estrictamente tipado para eliminar una planificación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación a eliminar.")


class GetCNBAreaByIdInput(BaseModel):
    """Input estrictamente tipado para consultar un área curricular por ID."""
    id_area: str = Field(..., description="ID de MongoDB (24 caracteres hex) del área curricular.")


class GetCNBSubareaByIdInput(BaseModel):
    """Input strictly tipado para consultar una subárea por ID."""
    id_subarea: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea.")


class SaveAssessmentInstrumentInput(BaseModel):
    """Input estrictamente tipado para guardar un instrumento de evaluación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación.")
    id_fila: int = Field(..., description="ID de fila dentro de la planificación.")
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la actividad evaluada.")
    tipo: str = Field(..., description="Tipo de instrumento: 'lista_cotejo', 'rubrica', 'escala_rango'.")
    titulo: str = Field(..., description="Título descriptivo del instrumento.")
    instrumento_generado: Dict[str, Any] = Field(..., description="Estructura completa del instrumento generado.")


class GetAssessmentInstrumentByIdInput(BaseModel):
    """Input estrictamente tipado para consultar un instrumento por ID."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres hex) del instrumento de evaluación.")


class UpdateAssessmentInstrumentInput(BaseModel):
    """Input estrictamente tipado para actualizar un instrumento de evaluación."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres hex) del instrumento a actualizar.")
    tipo_instrumento: Optional[str] = Field(default=None, description="Tipo de instrumento actualizado.")
    actividad_evaluada: Optional[str] = Field(default=None, description="Actividad evaluada actualizada.")
    fase_actividad: Optional[str] = Field(default=None, description="Fase de actividad actualizada.")
    criterios: Optional[List[Dict[str, Any]]] = Field(default=None, description="Criterios actualizados.")


class DeleteAssessmentInstrumentInput(BaseModel):
    """Input estrictamente tipado para eliminar un instrumento de evaluación."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres hex) del instrumento a eliminar.")


class SaveMultimodalResourceInput(BaseModel):
    """Input estrictamente tipado para guardar un recurso multimodal."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación.")
    id_fila: int = Field(..., description="ID de fila dentro de la planificación.")
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la actividad de aprendizaje.")
    tipo: str = Field(..., description="Tipo de recurso: 'video', 'documento', 'imagen', 'simulacion', 'lectura'.")
    titulo: str = Field(..., description="Título descriptivo del recurso didáctico.")
    url: str = Field(..., description="Enlace URL del recurso (web o fuente externa).")


class GetMultimodalResourceByIdInput(BaseModel):
    """Input estrictamente tipado para consultar un recurso multimodal por ID."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres hex) del recurso multimodal.")


class UpdateMultimodalResourceInput(BaseModel):
    """Input estrictamente tipado para actualizar un recurso multimodal."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres hex) del recurso a actualizar.")
    tipo_recurso: Optional[str] = Field(default=None, description="Tipo de recurso actualizado.")
    titulo: Optional[str] = Field(default=None, description="Título actualizado.")
    url: Optional[str] = Field(default=None, description="URL actualizada.")
    fase_pedagogica: Optional[str] = Field(default=None, description="Fase pedagógica actualizada.")
    descripcion: Optional[str] = Field(default=None, description="Descripción actualizada.")


class DeleteMultimodalResourceInput(BaseModel):
    """Input estrictamente tipado para eliminar un recurso multimodal."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres hex) del recurso a eliminar.")


class GetTopFrequentCoursesInput(BaseModel):
    """Input estrictamente tipado para consultar los cursos más frecuentes."""
    limit: int = Field(default=5, description="Cantidad máxima de cursos a retornar.")


class GetRecentLessonPlansInput(BaseModel):
    """Input estrictamente tipado para consultar las planificaciones recientes."""
    limit: int = Field(default=5, description="Cantidad de planificaciones recientes a retornar.")


class GetLatestPlanInstrumentsAndResourcesInput(BaseModel):
    """Input estrictamente tipado para consultar últimos instrumentos y recursos."""
    pass


class GetPaginatedLessonPlansInput(BaseModel):
    """Input estrictamente tipado para consultar planificaciones paginadas."""
    page: int = Field(default=1, description="Número de página (iniciando en 1).")
    page_size: int = Field(default=10, description="Tamaño de página.")


class GetFullLessonPlanDetailsInput(BaseModel):
    """Input estrictamente tipado para consultar el detalle completo de una planificación."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación.")


class GetCNBCareersListInput(BaseModel):
    """Input estrictamente tipado para la lista de carreras del CNB."""
    pass


class GetCNBAreasByCareerInput(BaseModel):
    """Input estrictamente tipado para consultar las áreas del CNB por carrera."""
    carrera: str = Field(..., description="Nombre o filtro de la carrera.")
    page: int = Field(default=1, description="Número de página.")
    limit: int = Field(default=10, description="Límite por página.")


class GetCNBSubareasByAreaIdInput(BaseModel):
    """Input estrictamente tipado para consultar subáreas por ID de área."""
    id_area: str = Field(..., description="ID del área curricular.")
    page: int = Field(default=1, description="Número de página.")
    limit: int = Field(default=10, description="Límite por página.")


class SearchCurriculumVectorDBInput(BaseModel):
    """Input estrictamente tipado para buscar en la base de datos vectorial del CNB."""
    query: str = Field(..., description="Consulta semántica para buscar competencias o contenidos relevantes.")
    id_subarea_relacionada: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea curricular. Obligatorio.")
    limit: int = Field(default=5, description="Número de resultados más similares a retornar.")


class GetSubareaVectorEmbeddingsInput(BaseModel):
    """Input estrictamente tipado para consultar el vector de embedding de una subárea."""
    id_subarea_relacionada: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea curricular. Obligatorio.")
    limit: int = Field(default=5, description="Cantidad máxima de resultados a retornar.")


class GenerateSubareaVectorEmbeddingsInput(BaseModel):
    """Input estrictamente tipado para generar embeddings de una subárea."""
    id_subarea_relacionada: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la subárea a vectorizar.")
