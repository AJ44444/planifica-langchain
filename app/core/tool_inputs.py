from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ==============================================================================
# 1. MODELOS DE DATOS DE PLANIFICACIÓN Y ESTRUCTURAS CURRICULARES DE SUBÁREA
# ==============================================================================

class Contenido(BaseModel):
    """Modelo de contenido temático."""
    id_contenido: str = Field(..., description="Identificador del contenido.")
    descripcion: str = Field(..., description="Descripción del contenido.")


class IndicadorLogro(BaseModel):
    """Modelo de indicador de logro."""
    id_indicador: str = Field(..., description="Identificador del indicador de logro.")
    descripcion: str = Field(..., description="Descripción del indicador de logro.")
    contenidos: List[Contenido] = Field(default_factory=list, description="Lista de contenidos asociados.")


class CompetenciaEspecifica(BaseModel):
    """Modelo de competencia específica."""
    id_competencia: str = Field(..., description="Identificador de la competencia.")
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
    competencias_area: List[str] = Field(..., description="Lista de competencias del área.")
    actividades_sugeridas: List[str] = Field(..., description="Lista de actividades sugeridas.")
    criterios_evaluacion: List[str] = Field(..., description="Lista de criterios de evaluación.")
    subareas: List[Dict[str, Any]] = Field(..., description="Lista de subáreas pertenecientes al área.")


class MetadatosPlanInput(BaseModel):
    """Input para metadatos de una planificación."""
    carrera: str = Field(..., description="Nombre oficial de la carrera (ej. Bachillerato en Computación).")
    subarea_curricular: str = Field(..., description="Nombre de la subárea curricular.")
    estado: Optional[str] = Field(default="borrador", description="Estado del documento: 'borrador', 'publicado', 'archivado'.")


# ==============================================================================
# 2. ESQUEMAS DE ENTRADA ESTRICTAMENTE TIPADOS PARA HERRAMIENTAS SAVE (args_schema)
# ==============================================================================

class SaveCurricularStructureInput(BaseModel):
    """Input strictly typed for saving parsed CNB curricular structure."""
    nombre_carrera: str = Field(..., description="Nombre oficial de la carrera (ej. Bachillerato en Computación).")
    nombre_area: str = Field(..., description="Nombre del área curricular.")
    competencias_area: List[str] = Field(default_factory=list, description="Lista de competencias del área.")
    actividades_sugeridas: List[str] = Field(default_factory=list, description="Lista de actividades sugeridas del área.")
    criterios_evaluacion_sugeridos: List[str] = Field(default_factory=list, description="Lista de criterios de evaluación sugeridos.")
    subareas: List[Subarea] = Field(..., description="Lista de subáreas pertenecientes al área con sus competencias e indicadores.")


class SaveLessonPlanInput(BaseModel):
    """Input estrictamente tipado para guardar una planificación docente en MongoDB."""
    metadatos: MetadatosPlanInput = Field(..., description="Metadatos de la planificación.")
    encabezado: EncabezadoPlan = Field(..., description="Datos generales de encabezado del plan.")
    desarrollo_curricular: List[FilaCurricularPlan] = Field(..., description="Filas aplanadas de desarrollo curricular.")
    id_usuario: Optional[str] = Field(default="", description="ID del usuario opcional.")


class SaveAssessmentInstrumentInput(BaseModel):
    """Input estrictamente tipado para guardar un instrumento de evaluación."""
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la actividad evaluada.")
    tipo: Literal["rubrica", "lista_cotejo", "escala_rango"] = Field(..., description="Tipo de instrumento: 'lista_cotejo', 'rubrica', 'escala_rango'.")
    titulo: str = Field(..., description="Título descriptivo del instrumento.")
    instrumento_generado: InstrumentoGeneradoDetail = Field(..., description="Estructura completa del instrumento generado.")


class SaveMultimodalResourceInput(BaseModel):
    """Input estrictamente tipado para guardar un recurso multimodal."""
    id_actividad: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la actividad de aprendizaje.")
    tipo: Literal["video", "documento", "imagen", "simulacion", "lectura"] = Field(..., description="Tipo de recurso: 'video', 'documento', 'imagen', 'simulacion', 'lectura'.")
    titulo: str = Field(..., description="Título descriptivo del recurso didáctico.")
    url: str = Field(..., description="Enlace URL del recurso (web o fuente externa).")


# ==============================================================================
# 3. ESQUEMAS DE ENTRADA ESTRICTAMENTE TIPADOS PARA HERRAMIENTAS UPDATE (args_schema)
# ==============================================================================

class UpdateLessonPlanInput(BaseModel):
    """Input estrictamente tipado para actualizar una planificación docente. Excluye 'id_usuario'."""
    id_planificacion: str = Field(..., description="ID de MongoDB (24 caracteres hex) de la planificación a actualizar.")
    metadatos: Optional[MetadatosPlanInput] = Field(default=None, description="Metadatos actualizados opcionales.")
    encabezado: Optional[EncabezadoPlan] = Field(default=None, description="Datos de encabezado actualizados opcionales.")
    desarrollo_curricular: Optional[List[FilaCurricularPlan]] = Field(default=None, description="Desarrollo curricular actualizado opcional.")


class UpdateAssessmentInstrumentInput(BaseModel):
    """Input estrictamente tipado para actualizar un instrumento de evaluación. Excluye 'id_planificacion' e 'id_fila'."""
    id_instrumento: str = Field(..., description="ID de MongoDB (24 caracteres hex) del instrumento a actualizar.")
    id_actividad: Optional[str] = Field(default=None, description="ID de la actividad evaluada actualizado opcional.")
    tipo: Optional[Literal["rubrica", "lista_cotejo", "escala_rango"]] = Field(default=None, description="Tipo de instrumento actualizado opcional.")
    titulo: Optional[str] = Field(default=None, description="Título descriptivo actualizado opcional.")
    instrumento_generado: Optional[InstrumentoGeneradoDetail] = Field(default=None, description="Estructura completa del instrumento generado actualizada opcional.")


class UpdateMultimodalResourceInput(BaseModel):
    """Input estrictamente tipado para actualizar un recurso multimodal. Excluye 'id_planificacion' e 'id_fila'."""
    id_recurso: str = Field(..., description="ID de MongoDB (24 caracteres hex) del recurso a actualizar.")
    id_actividad: Optional[str] = Field(default=None, description="ID de la actividad de aprendizaje actualizado opcional.")
    tipo: Optional[Literal["video", "documento", "imagen", "simulacion", "lectura"]] = Field(default=None, description="Tipo de recurso actualizado opcional.")
    titulo: Optional[str] = Field(default=None, description="Título descriptivo actualizado opcional.")
    url: Optional[str] = Field(default=None, description="Enlace URL del recurso actualizado opcional.")
