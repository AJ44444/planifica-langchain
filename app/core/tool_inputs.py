from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class Contenido(BaseModel):
    """Thematic content model."""
    id_contenido: str = Field(..., description="Content identifier.")
    descripcion: str = Field(..., description="Description of the thematic content.")


class IndicadorLogro(BaseModel):
    """Achievement indicator model."""
    id_indicador: str = Field(..., description="Achievement indicator identifier.")
    descripcion: str = Field(..., description="Description of the achievement indicator.")
    contenidos: List[Contenido] = Field(default_factory=list, description="List of associated thematic contents.")


class CompetenciaEspecifica(BaseModel):
    """Specific competency model."""
    id_competencia: str = Field(..., description="Competency identifier.")
    descripcion: str = Field(..., description="Description of the competency.")
    indicadores_logro: List[IndicadorLogro] = Field(default_factory=list, description="List of achievement indicators.")


class Subarea(BaseModel):
    """Curricular subarea model."""
    nombre_subarea: str = Field(..., description="Name of the curricular subarea.")
    competencias: List[CompetenciaEspecifica] = Field(default_factory=list, description="List of subarea competencies.")


class EncabezadoPlan(BaseModel):
    """Informational header of a lesson plan."""
    centro_educativo: str = Field(..., description="Name of the educational center.")
    lugar: str = Field(..., description="Geographical location (municipality/department).")
    grado: str = Field(..., description="Academic grade (e.g. '4th', '1st Basic').")
    seccion: str = Field(..., description="Academic section (e.g. 'A').")
    duracion: str = Field(..., description="Duration (e.g. '1 week', '1 bimonth').")
    cantidad_periodos: int = Field(..., description="Total number of class periods.")
    duracion_periodos: int = Field(..., description="Duration of each period in minutes.")


class ActividadAprendizaje(BaseModel):
    """Pedagogical learning activity."""
    id_actividad: Optional[str] = Field(default=None, description="Unique activity ID.")
    fase: Literal["inicio", "desarrollo", "cierre"] = Field(..., description="Pedagogical phase of the activity.")
    descripcion: str = Field(..., description="Impersonal description starting with an infinitive verb.")


class IndicadorPlanItem(BaseModel):
    """Indicator item with associated contents."""
    indicador: str = Field(..., description="Description of the achievement indicator.")
    contenidos: List[str] = Field(..., description="List of associated thematic contents.")


class FilaCurricularPlan(BaseModel):
    """Flattened curricular development row."""
    id_fila: int = Field(..., description="Ordinal row ID.")
    competencia: str = Field(..., description="Description of the competency.")
    indicadores_logro: List[IndicadorPlanItem] = Field(..., description="List of achievement indicators.")
    actividades_aprendizaje: List[ActividadAprendizaje] = Field(..., description="List of learning activities.")


class PlanificacionClase(BaseModel):
    """Complete structure of a teacher's lesson plan."""
    encabezado: EncabezadoPlan
    desarrollo_curricular: List[FilaCurricularPlan]


class CriterioEvaluacion(BaseModel):
    """Evaluation criterion for an assessment instrument."""
    nombre: str = Field(..., description="Name of the criterion.")
    definiciones: List[str] = Field(..., description="Definitions or performance level descriptions.")


class InstrumentoGeneradoDetail(BaseModel):
    """Technical details of the generated assessment instrument."""
    escala: List[str] = Field(..., description="Performance scale (e.g. ['Excellent', 'Good']).")
    criterios: List[CriterioEvaluacion] = Field(..., description="List of evaluation criteria.")


class CurricularAreaModel(BaseModel):
    """Model representing a Curricular Area."""
    id_area: str = Field(..., description="Unique numeric identifier of the curricular area.")
    nombre_area: str = Field(..., description="Name of the curricular area.")
    competencias_area: List[str] = Field(..., description="List of area competencies.")
    actividades_sugeridas: List[str] = Field(..., description="List of suggested activities.")
    criterios_evaluacion: List[str] = Field(..., description="List of evaluation criteria.")
    subareas: List[Dict[str, Any]] = Field(..., description="List of subareas belonging to the area.")


class MetadatosPlanInput(BaseModel):
    """Input metadata for a lesson plan."""
    carrera: str = Field(..., description="Official career name (e.g. High School in Computer Science).")
    subarea_curricular: str = Field(..., description="Name of the curricular subarea.")
    estado: Optional[str] = Field(default="borrador", description="Document status: 'borrador', 'publicado', 'archivado'.")


class SaveCurricularStructureInput(BaseModel):
    """Input strictly typed for saving parsed CNB curricular structure."""
    nombre_carrera: str = Field(..., description="Official career name (e.g. High School in Computer Science).")
    nombre_area: str = Field(..., description="Name of the curricular area.")
    competencias_area: List[str] = Field(default_factory=list, description="List of area competencies.")
    actividades_sugeridas: List[str] = Field(default_factory=list, description="List of suggested area activities.")
    criterios_evaluacion_sugeridos: List[str] = Field(default_factory=list, description="List of suggested evaluation criteria.")
    subareas: List[Subarea] = Field(..., description="List of subareas belonging to the area with their competencies and indicators.")


class SaveLessonPlanInput(BaseModel):
    """Strictly typed input to save a teacher's lesson plan in MongoDB."""
    metadatos: MetadatosPlanInput = Field(..., description="Lesson plan metadata.")
    encabezado: EncabezadoPlan = Field(..., description="General header data of the plan.")
    desarrollo_curricular: List[FilaCurricularPlan] = Field(..., description="Flattened curricular development rows.")
    id_usuario: Optional[str] = Field(default="", description="Optional user ID.")


class SaveAssessmentInstrumentInput(BaseModel):
    """Strictly typed input to save an assessment instrument."""
    id_actividad: str = Field(..., description="MongoDB ID (24-character hex) of the evaluated activity.")
    tipo: Literal["rubrica", "lista_cotejo", "escala_rango"] = Field(..., description="Instrument type: 'lista_cotejo', 'rubrica', 'escala_rango'.")
    titulo: str = Field(..., description="Descriptive title of the instrument.")
    instrumento_generado: InstrumentoGeneradoDetail = Field(..., description="Complete structure of the generated instrument.")


class SaveMultimodalResourceInput(BaseModel):
    """Strictly typed input to save a multimodal resource."""
    id_actividad: str = Field(..., description="MongoDB ID (24-character hex) of the learning activity.")
    tipo: Literal["video", "documento", "imagen", "simulacion", "lectura"] = Field(..., description="Resource type: 'video', 'documento', 'imagen', 'simulacion', 'lectura'.")
    titulo: str = Field(..., description="Descriptive title of the educational resource.")
    url: str = Field(..., description="URL link of the resource (web or external source).")


class UpdateLessonPlanInput(BaseModel):
    """Strictly typed input to update a teacher's lesson plan. Excludes 'id_usuario'."""
    id_planificacion: str = Field(..., description="MongoDB ID (24-character hex) of the lesson plan to update.")
    metadatos: Optional[MetadatosPlanInput] = Field(default=None, description="Optional updated metadata.")
    encabezado: Optional[EncabezadoPlan] = Field(default=None, description="Optional updated header data.")
    desarrollo_curricular: Optional[List[FilaCurricularPlan]] = Field(default=None, description="Optional updated curricular development.")


class UpdateAssessmentInstrumentInput(BaseModel):
    """Strictly typed input to update an assessment instrument. Excludes 'id_planificacion' and 'id_fila'."""
    id_instrumento: str = Field(..., description="MongoDB ID (24-character hex) of the instrument to update.")
    id_actividad: Optional[str] = Field(default=None, description="Optional updated evaluated activity ID.")
    tipo: Optional[Literal["rubrica", "lista_cotejo", "escala_rango"]] = Field(default=None, description="Optional updated instrument type.")
    titulo: Optional[str] = Field(default=None, description="Optional updated descriptive title.")
    instrumento_generado: Optional[InstrumentoGeneradoDetail] = Field(default=None, description="Optional updated complete structure of the generated instrument.")


class UpdateMultimodalResourceInput(BaseModel):
    """Strictly typed input to update a multimodal resource. Excludes 'id_planificacion' and 'id_fila'."""
    id_recurso: str = Field(..., description="MongoDB ID (24-character hex) of the resource to update.")
    id_actividad: Optional[str] = Field(default=None, description="Optional updated learning activity ID.")
    tipo: Optional[Literal["video", "documento", "imagen", "simulacion", "lectura"]] = Field(default=None, description="Optional updated resource type.")
    titulo: Optional[str] = Field(default=None, description="Optional updated descriptive title.")
    url: Optional[str] = Field(default=None, description="Optional updated URL link.")
