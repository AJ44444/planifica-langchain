import os
import json
import time
from datetime import datetime, timezone
from typing import Union, Dict, Any, List, Optional
from bson import ObjectId
from bson.timestamp import Timestamp
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from core.config import MONGODB_URI, DB_NAME
from core.response_formats import (
    Subarea,
    EncabezadoPlan,
    FilaCurricularPlan,
    InstrumentoGeneradoDetail,
)
from core.tool_inputs import (
    MetadatosPlanInput,
    SaveCurricularStructureInput,
    SaveLessonPlanInput,
    GetPlanificationByIdInput,
    UpdateLessonPlanInput,
    DeleteLessonPlanInput,
    SaveAssessmentInstrumentInput,
    GetAssessmentInstrumentByIdInput,
    UpdateAssessmentInstrumentInput,
    DeleteAssessmentInstrumentInput,
    SaveMultimodalResourceInput,
    GetMultimodalResourceByIdInput,
    UpdateMultimodalResourceInput,
    DeleteMultimodalResourceInput,
    GetTopFrequentCoursesInput,
    GetRecentLessonPlansInput,
    GetLatestPlanInstrumentsAndResourcesInput,
    GetPaginatedLessonPlansInput,
    GetFullLessonPlanDetailsInput,
    GetCNBAreasByCareersInput,
    GetCNBSubareasByAreaIdInput,
)


def _get_bson_timestamp() -> Timestamp:
    """Genera un objeto BSON Timestamp de MongoDB."""
    return Timestamp(int(time.time()), 1)


def get_mongo_client() -> MongoClient:
    """Retorna una instancia de MongoClient utilizando la URI configurada."""
    if not MONGODB_URI:
        raise ValueError("La variable MONGODB_URI no está configurada en .env.")
    return MongoClient(MONGODB_URI)


def get_db():
    """Retorna la base de datos de MongoDB a partir de DB_NAME o la base por defecto de MONGODB_URI."""
    client = get_mongo_client()
    if DB_NAME:
        return client[DB_NAME]
    try:
        db = client.get_default_database()
        if db is not None:
            return db
    except Exception:
        pass
    raise ValueError("No se especificó la base de datos de MongoDB. Configura DB_NAME en .env o inclúyela en la MONGODB_URI.")


def extract_user_id_from_config(config: Optional[Any] = None) -> str:
    """
    Extrae de forma segura el ID del usuario autenticado del objeto RunnableConfig de LangGraph.
    Prioriza 'langgraph_auth_user' inyectado por auth_handler y la clave 'id_usuario'.
    """
    if not config:
        return ""

    configurable = {}
    if isinstance(config, dict):
        configurable = config.get("configurable", {})
    elif hasattr(config, "configurable"):
        configurable = getattr(config, "configurable", {})
    elif hasattr(config, "get"):
        configurable = config.get("configurable", {})

    auth_user = configurable.get("langgraph_auth_user")
    if isinstance(auth_user, dict):
        identity = auth_user.get("identity")
        if identity:
            return str(identity)
    elif hasattr(auth_user, "identity"):
        return str(getattr(auth_user, "identity"))

    id_usuario = configurable.get("id_usuario")
    if id_usuario:
        return str(id_usuario)

    return ""


class JSONEncoderCustom(json.JSONEncoder):
    """Codificador de JSON personalizado para manejar ObjectId, Timestamp y datetime de MongoDB."""
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, Timestamp):
            return o.as_datetime().isoformat()
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _to_dict(obj: Any) -> dict:
    """Convierte un objeto Pydantic o diccionario en dict de Python."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def _ensure_object_id(val: Any) -> ObjectId:
    """Convierte una cadena hexadecimal de 24 caracteres en ObjectId de MongoDB."""
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str) and len(val.strip()) == 24:
        try:
            return ObjectId(val.strip())
        except Exception:
            pass
    return ObjectId()


def _clean_updates(updates: dict) -> dict:
    """Limpia el diccionario de actualización quitando _id y convirtiendo IDs de referencia."""
    clean = _to_dict(updates)
    if "_id" in clean:
        del clean["_id"]
    for key in ["id_area", "id_subarea_relacionada", "id_usuario", "id_planificacion", "id_actividad"]:
        if key in clean and isinstance(clean[key], str) and len(clean[key].strip()) == 24:
            try:
                clean[key] = ObjectId(clean[key].strip())
            except Exception:
                pass
    return clean


# ==========================================
# FUNCIONES INTERNAS DE PERSISTENCIA INDIVIDUAL (Sin anotación @tool)
# ==========================================

def insert_cnb_area_doc(data: dict) -> ObjectId:
    """Función interna individual para insertar un área curricular en 'cnb_areas'."""
    db = get_db()
    nombre_carrera = data.get("nombre_carrera", "Sin Carrera")
    nombre_area = data.get("nombre_area", "Sin Área")

    def _format_items(items):
        if not items:
            return []
        result = []
        for item in items:
            if isinstance(item, str):
                result.append({"descripcion": item})
            elif isinstance(item, dict):
                result.append(item)
        return result

    area_doc = {
        "nombre_carrera": nombre_carrera,
        "nombre_area": nombre_area,
        "competencias_area": _format_items(data.get("competencias_area", [])),
        "actividades_sugeridas": _format_items(data.get("actividades_sugeridas", [])),
        "criterios_evaluacion_sugeridos": _format_items(data.get("criterios_evaluacion_sugeridos", []))
    }

    res = db["cnb_areas"].insert_one(area_doc)
    return res.inserted_id


def insert_cnb_subarea_doc(data: dict) -> ObjectId:
    """Función interna individual para insertar una subárea curricular en 'cnb_subareas'."""
    db = get_db()
    id_area = data.get("id_area")
    if isinstance(id_area, str):
        id_area = ObjectId(id_area)

    subarea_doc = {
        "id_area": id_area,
        "nombre_carrera": data.get("nombre_carrera", ""),
        "nombre_subarea": data.get("nombre_subarea", "Sin Subárea"),
        "competencias": data.get("competencias", [])
    }

    res = db["cnb_subareas"].insert_one(subarea_doc)
    return res.inserted_id


def insert_cnb_vector_doc(data: dict) -> ObjectId:
    """Función interna individual para insertar un nodo en 'cnb_vectores'."""
    db = get_db()
    id_subarea = data.get("id_subarea_relacionada")
    if isinstance(id_subarea, str):
        id_subarea = ObjectId(id_subarea)

    doc = {
        "id_subarea_relacionada": id_subarea,
        "nombre_subarea": data.get("nombre_subarea", ""),
        "tipo_nodo": data.get("tipo_nodo", "competencia"),
        "referencia_jerarquica": data.get("referencia_jerarquica", []),
        "texto_a_buscar": data.get("texto_a_buscar", ""),
        "vector_embedding": data.get("vector_embedding", []),
        "vector_estado": data.get("vector_estado", False)
    }

    res = db["cnb_vectores"].insert_one(doc)
    return res.inserted_id


# ==========================================
# 1. TOOL PRINCIPAL: ESTRUCTURA CURRICULAR COMPLETA
# ==========================================

@tool("save_curricular_structure", args_schema=SaveCurricularStructureInput)
def save_curricular_structure(
    nombre_carrera: str,
    nombre_area: str,
    competencias_area: List[str],
    actividades_sugeridas: List[str],
    criterios_evaluacion_sugeridos: List[str],
    subareas: List[Union[dict, Subarea]]
) -> str:
    """
    Guarda la estructura curricular completa del CNB en MongoDB (colecciones 'cnb_areas', 'cnb_subareas' y 'cnb_vectores').
    Los registros vectoriales se crean con 'vector_embedding' vacío [] y 'vector_estado' = False.
    """
    try:
        subareas_dicts = [_to_dict(s) for s in subareas]
        area_data = {
            "nombre_carrera": nombre_carrera,
            "nombre_area": nombre_area,
            "competencias_area": competencias_area,
            "actividades_sugeridas": actividades_sugeridas,
            "criterios_evaluacion_sugeridos": criterios_evaluacion_sugeridos,
            "subareas": subareas_dicts
        }

        area_id = insert_cnb_area_doc(area_data)

        subareas_inserted = []
        vectores_nodes_created = 0

        for sub in subareas_dicts:
            nombre_subarea = sub.get("nombre_subarea", "Sin Subárea")
            competencias = sub.get("competencias", [])

            subarea_data = {
                "id_area": area_id,
                "nombre_carrera": nombre_carrera,
                "nombre_subarea": nombre_subarea,
                "competencias": competencias
            }
            sub_id = insert_cnb_subarea_doc(subarea_data)
            subareas_inserted.append({"id_subarea": str(sub_id), "nombre_subarea": nombre_subarea})

            for comp in competencias:
                comp_dict = _to_dict(comp)
                comp_id = str(comp_dict.get("id_competencia", ""))
                comp_desc = comp_dict.get("descripcion", "")
                comp_text = f"Competencia {comp_id}: {comp_desc}".strip()

                insert_cnb_vector_doc({
                    "id_subarea_relacionada": sub_id,
                    "nombre_subarea": nombre_subarea,
                    "tipo_nodo": "competencia",
                    "referencia_jerarquica": [f"Competencia {comp_id}"],
                    "texto_a_buscar": comp_text,
                    "vector_embedding": [],
                    "vector_estado": False
                })
                vectores_nodes_created += 1

                for ind in comp_dict.get("indicadores_logro", []):
                    ind_dict = _to_dict(ind)
                    ind_id = str(ind_dict.get("id_indicador", ""))
                    ind_desc = ind_dict.get("descripcion", "")
                    ind_text = f"Indicador {ind_id}: {ind_desc}".strip()

                    insert_cnb_vector_doc({
                        "id_subarea_relacionada": sub_id,
                        "nombre_subarea": nombre_subarea,
                        "tipo_nodo": "indicador",
                        "referencia_jerarquica": [f"Competencia {comp_id}", f"Indicador {ind_id}"],
                        "texto_a_buscar": ind_text,
                        "vector_embedding": [],
                        "vector_estado": False
                    })
                    vectores_nodes_created += 1

                    for cnt in ind_dict.get("contenidos", []):
                        cnt_dict = _to_dict(cnt)
                        cnt_id = str(cnt_dict.get("id_contenido", ""))
                        cnt_desc = cnt_dict.get("descripcion", "")
                        cnt_text = f"Contenido {cnt_id}: {cnt_desc}".strip()

                        insert_cnb_vector_doc({
                            "id_subarea_relacionada": sub_id,
                            "nombre_subarea": nombre_subarea,
                            "tipo_nodo": "contenido",
                            "referencia_jerarquica": [f"Competencia {comp_id}", f"Indicador {ind_id}", f"Contenido {cnt_id}"],
                            "texto_a_buscar": cnt_text,
                            "vector_embedding": [],
                            "vector_estado": False
                        })
                        vectores_nodes_created += 1

        response = {
            "status": "success",
            "message": "Estructura curricular guardada exitosamente.",
            "id_area": str(area_id),
            "subareas_insertadas": subareas_inserted,
            "nodos_vectoriales_creados": vectores_nodes_created
        }
        return json.dumps(response, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar la estructura curricular: {str(e)}"})


# ==========================================
# 2. CRUD Y SEGURIDAD: PLANIFICACIONES GENERADAS (planificaciones_generadas)
# ==========================================

@tool("save_lesson_plan", args_schema=SaveLessonPlanInput)
def save_lesson_plan(
    metadatos: Union[dict, MetadatosPlanInput],
    encabezado: Union[dict, EncabezadoPlan],
    desarrollo_curricular: List[Union[dict, FilaCurricularPlan]],
    id_usuario: str = ""
) -> str:
    """
    CRUD Create: Guarda/crea una nueva planificación docente en 'planificaciones_generadas'.
    """
    try:
        db = get_db()
        user_obj_id = _ensure_object_id(id_usuario) if id_usuario else ObjectId()

        meta_dict = _to_dict(metadatos)
        enc_dict = _to_dict(encabezado)

        metadatos_doc = {
            "carrera": str(meta_dict.get("carrera", "")),
            "subarea_curricular": str(meta_dict.get("subarea_curricular", "")),
            "fecha_creacion": _get_bson_timestamp(),
            "estado": str(meta_dict.get("estado", "finalizado"))
        }

        formatted_desarrollo = []
        for fila in desarrollo_curricular:
            fila_dict = _to_dict(fila)
            acts = fila_dict.get("actividades_aprendizaje", [])
            formatted_acts = []
            for act in acts:
                act_dict = _to_dict(act)
                act_id_val = act_dict.get("id_actividad")
                act_dict["id_actividad"] = _ensure_object_id(act_id_val) if act_id_val else ObjectId()
                formatted_acts.append(act_dict)

            fila_dict["actividades_aprendizaje"] = formatted_acts
            formatted_desarrollo.append(fila_dict)

        doc = {
            "id_usuario": user_obj_id,
            "metadatos": metadatos_doc,
            "encabezado": {
                "centro_educativo": str(enc_dict.get("centro_educativo", "")),
                "lugar": str(enc_dict.get("lugar", "")),
                "grado": str(enc_dict.get("grado", "")),
                "seccion": str(enc_dict.get("seccion", "")),
                "nombre_docente": str(enc_dict.get("nombre_docente", "")),
                "duracion": int(enc_dict.get("duracion", 1))
            },
            "desarrollo_curricular": formatted_desarrollo
        }

        res = db["planificaciones_generadas"].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Planificación de clase creada exitosamente.",
            "id_planificacion": str(res.inserted_id),
            "id_usuario": str(user_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al crear planificación: {str(e)}"})


@tool("get_planification_by_id", args_schema=GetPlanificationByIdInput)
def get_planification_by_id(id_planificacion: str, id_usuario: str = "") -> str:
    """CRUD Read & Privacidad: Busca y recupera una planificación docente por su ID en MongoDB."""
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())
        
        query = {"_id": obj_id}
        if id_usuario and len(id_usuario.strip()) == 24:
            query["id_usuario"] = ObjectId(id_usuario.strip())

        plan = db["planificaciones_generadas"].find_one(query)
        if not plan:
            return json.dumps({
                "status": "error",
                "message": f"Acceso denegado o planificación con _id '{id_planificacion}' no encontrada para este usuario."
            }, ensure_ascii=False)

        return json.dumps({"status": "success", "planificacion": plan}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar planificación: {str(e)}"})


@tool("update_lesson_plan", args_schema=UpdateLessonPlanInput)
def update_lesson_plan(id_planificacion: str, update_data: Dict[str, Any], id_usuario: str = "") -> str:
    """CRUD Update & Privacidad: Actualiza los campos solicitados mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())
        updates = _clean_updates(update_data)

        if not updates:
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        query = {"_id": obj_id}
        if id_usuario and len(id_usuario.strip()) == 24:
            query["id_usuario"] = ObjectId(id_usuario.strip())

        res = db["planificaciones_generadas"].update_one(query, {"$set": updates})

        if res.matched_count == 0:
            return json.dumps({
                "status": "error",
                "message": f"Acceso denegado o planificación '{id_planificacion}' no encontrada."
            }, ensure_ascii=False)

        return json.dumps({
            "status": "success",
            "message": f"Planificación '{id_planificacion}' actualizada exitosamente mediante $set.",
            "modified_count": res.modified_count
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar la planificación: {str(e)}"})


@tool("delete_lesson_plan", args_schema=DeleteLessonPlanInput)
def delete_lesson_plan(id_planificacion: str, id_usuario: str = "", confirm: bool = True) -> str:
    """CRUD Delete & Privacidad: Elimina una planificación por su ID en MongoDB validando propiedad y confirmación."""
    try:
        if not confirm:
            return json.dumps({
                "status": "pending_confirmation",
                "message": f"CONFIRMACIÓN REQUERIDA: ¿Está seguro de eliminar permanentemente la planificación '{id_planificacion}'?"
            }, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        query = {"_id": obj_id}
        if id_usuario and len(id_usuario.strip()) == 24:
            query["id_usuario"] = ObjectId(id_usuario.strip())

        res = db["planificaciones_generadas"].delete_one(query)

        if res.deleted_count == 0:
            return json.dumps({
                "status": "error",
                "message": f"Acceso denegado o planificación '{id_planificacion}' no encontrada."
            }, ensure_ascii=False)

        return json.dumps({
            "status": "success",
            "message": f"Planificación '{id_planificacion}' eliminada exitosamente."
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar la planificación: {str(e)}"})


# ==========================================
# 3. CRUD: ÁREAS CURRICULARES (cnb_areas)
# ==========================================

@tool("get_cnb_area_by_id")
def get_cnb_area_by_id(id_area: str) -> str:
    """CRUD Read: Busca un área curricular del CNB por su ID de MongoDB."""
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        area = db["cnb_areas"].find_one({"_id": obj_id})
        if not area:
            return json.dumps({"status": "error", "message": f"Área curricular con _id '{id_area}' no encontrada."})
        return json.dumps({"status": "success", "area": area}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer área curricular: {str(e)}"})


@tool("update_cnb_area")
def update_cnb_area(id_area: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza campos específicos de un área curricular mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        updates = _clean_updates(update_data)

        res = db["cnb_areas"].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Área curricular '{id_area}' no encontrada."})

        return json.dumps({"status": "success", "message": f"Área '{id_area}' actualizada exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar área curricular: {str(e)}"})


@tool("delete_cnb_area")
def delete_cnb_area(id_area: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un área curricular en 'cnb_areas' por su ID tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar área '{id_area}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_area.strip())
        res = db["cnb_areas"].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Área curricular '{id_area}' no encontrada."})

        return json.dumps({"status": "success", "message": f"Área '{id_area}' eliminada exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar área curricular: {str(e)}"})


# ==========================================
# 4. CRUD: SUBÁREAS CURRICULARES (cnb_subareas)
# ==========================================

@tool("get_cnb_subarea_by_id")
def get_cnb_subarea_by_id(id_subarea: str) -> str:
    """CRUD Read: Busca una subárea curricular por su ID de MongoDB en 'cnb_subareas'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        sub = db["cnb_subareas"].find_one({"_id": obj_id})
        if not sub:
            return json.dumps({"status": "error", "message": f"Subárea '{id_subarea}' no encontrada."})
        return json.dumps({"status": "success", "subarea": sub}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer subárea: {str(e)}"})


@tool("update_cnb_subarea")
def update_cnb_subarea(id_subarea: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza campos específicos de una subárea en 'cnb_subareas' mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        updates = _clean_updates(update_data)

        res = db["cnb_subareas"].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Subárea '{id_subarea}' no encontrada."})

        return json.dumps({"status": "success", "message": f"Subárea '{id_subarea}' actualizada exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar subárea: {str(e)}"})


@tool("delete_cnb_subarea")
def delete_cnb_subarea(id_subarea: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina una subárea curricular por su ID en 'cnb_subareas' tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar subárea '{id_subarea}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        res = db["cnb_subareas"].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Subárea '{id_subarea}' no encontrada."})

        return json.dumps({"status": "success", "message": f"Subárea '{id_subarea}' eliminada exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar subárea: {str(e)}"})


# ==========================================
# 5. CRUD: VECTORES DE BÚSQUEDA (cnb_vectores)
# ==========================================

@tool("get_cnb_vector_by_id")
def get_cnb_vector_by_id(id_vector: str) -> str:
    """CRUD Read: Obtiene un nodo vectorial de 'cnb_vectores' por su _id."""
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        vec = db["cnb_vectores"].find_one({"_id": obj_id})
        if not vec:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})
        return json.dumps({"status": "success", "vector": vec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer vector: {str(e)}"})


@tool("update_cnb_vector")
def update_cnb_vector(id_vector: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza los campos de un registro en 'cnb_vectores' mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        updates = _clean_updates(update_data)

        res = db["cnb_vectores"].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar vector: {str(e)}"})


@tool("delete_cnb_vector")
def delete_cnb_vector(id_vector: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un registro vectorial en 'cnb_vectores' por su _id tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar vector '{id_vector}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        res = db["cnb_vectores"].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' eliminado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar vector: {str(e)}"})


# ==========================================
# 6. CRUD: INSTRUMENTOS DE EVALUACIÓN (instrumentos_evaluacion)
# ==========================================

@tool("save_assessment_instrument", args_schema=SaveAssessmentInstrumentInput)
def save_assessment_instrument(
    id_planificacion: str,
    id_fila_curricular: int,
    id_actividad: str,
    tipo: str,
    titulo: str,
    instrumento_generado: Union[dict, InstrumentoGeneradoDetail]
) -> str:
    """CRUD Create: Guarda un instrumento de evaluación en 'instrumentos_evaluacion'."""
    try:
        db = get_db()
        plan_obj_id = _ensure_object_id(id_planificacion)
        act_obj_id = _ensure_object_id(id_actividad)
        inst_gen_dict = _to_dict(instrumento_generado)

        doc = {
            "id_planificacion": plan_obj_id,
            "id_fila_curricular": int(id_fila_curricular),
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "instrumento_generado": inst_gen_dict
        }

        res = db["instrumentos_evaluacion"].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Instrumento de evaluación guardado exitosamente.",
            "id_instrumento": str(res.inserted_id),
            "id_planificacion": str(plan_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el instrumento de evaluación: {str(e)}"})


@tool("get_assessment_instrument_by_id", args_schema=GetAssessmentInstrumentByIdInput)
def get_assessment_instrument_by_id(id_instrumento: str) -> str:
    """CRUD Read: Obtiene un instrumento de evaluación por su ID de MongoDB en 'instrumentos_evaluacion'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        inst = db["instrumentos_evaluacion"].find_one({"_id": obj_id})
        if not inst:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})
        return json.dumps({"status": "success", "instrumento": inst}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar instrumento de evaluación: {str(e)}"})


@tool("update_assessment_instrument", args_schema=UpdateAssessmentInstrumentInput)
def update_assessment_instrument(id_instrumento: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza los datos específicos de un instrumento de evaluación mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        updates = _clean_updates(update_data)

        res = db["instrumentos_evaluacion"].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Instrumento '{id_instrumento}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar instrumento de evaluación: {str(e)}"})


@tool("delete_assessment_instrument", args_schema=DeleteAssessmentInstrumentInput)
def delete_assessment_instrument(id_instrumento: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un instrumento de evaluación por su ID tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar instrumento '{id_instrumento}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        res = db["instrumentos_evaluacion"].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Instrumento '{id_instrumento}' eliminado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar instrumento de evaluación: {str(e)}"})


# ==========================================
# 7. CRUD: RECURSOS MULTIMODALES (recursos_multimodales)
# ==========================================

@tool("save_multimodal_resource", args_schema=SaveMultimodalResourceInput)
def save_multimodal_resource(
    id_planificacion: str,
    id_fila_curricular: int,
    id_actividad: str,
    tipo: str,
    titulo: str,
    url: str
) -> str:
    """CRUD Create: Guarda un recurso multimodal (video, imagen, audio, documento, sitio web) en 'recursos_multimodales'."""
    try:
        db = get_db()
        plan_obj_id = _ensure_object_id(id_planificacion)
        act_obj_id = _ensure_object_id(id_actividad)

        doc = {
            "id_planificacion": plan_obj_id,
            "id_fila_curricular": int(id_fila_curricular),
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "url": str(url)
        }

        res = db["recursos_multimodales"].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Recurso multimodal guardado exitosamente.",
            "id_recurso": str(res.inserted_id),
            "id_planificacion": str(plan_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el recurso multimodal: {str(e)}"})


@tool("get_multimodal_resource_by_id", args_schema=GetMultimodalResourceByIdInput)
def get_multimodal_resource_by_id(id_recurso: str) -> str:
    """CRUD Read: Obtiene un recurso multimodal por su ID de MongoDB en 'recursos_multimodales'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        rec = db["recursos_multimodales"].find_one({"_id": obj_id})
        if not rec:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})
        return json.dumps({"status": "success", "recurso": rec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer recurso multimodal: {str(e)}"})


@tool("update_multimodal_resource", args_schema=UpdateMultimodalResourceInput)
def update_multimodal_resource(id_recurso: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza campos específicos de un recurso multimodal mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        updates = _clean_updates(update_data)

        res = db["recursos_multimodales"].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Recurso '{id_recurso}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar recurso multimodal: {str(e)}"})


@tool("delete_multimodal_resource", args_schema=DeleteMultimodalResourceInput)
def delete_multimodal_resource(id_recurso: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un recurso multimodal por su ID en 'recursos_multimodales' tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar recurso '{id_recurso}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        res = db["recursos_multimodales"].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Recurso '{id_recurso}' eliminado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar recurso multimodal: {str(e)}"})


# ==========================================
# 8. HERRAMIENTAS DE CONSULTA Y SEGURIDAD (consultas_db.md)
# ==========================================

@tool("get_top_frequent_courses", args_schema=GetTopFrequentCoursesInput)
def get_top_frequent_courses(config: RunnableConfig = None, id_usuario: str = "", limit: int = 4) -> str:
    """1.A (consultas_db.md): Agrupa las planificaciones del usuario por subárea curricular y obtiene las más frecuentes."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        pipeline = [
            {"$match": {"id_usuario": user_obj_id}},
            {"$group": {"_id": "$metadatos.subarea_curricular", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]

        results = list(db["planificaciones_generadas"].aggregate(pipeline))
        return json.dumps({"status": "success", "id_usuario": effective_id, "top_cursos": results}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar top cursos: {str(e)}"})


@tool("get_recent_lesson_plans", args_schema=GetRecentLessonPlansInput)
def get_recent_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", limit: int = 3) -> str:
    """1.B (consultas_db.md): Recupera los datos del encabezado y metadatos de las últimas planificaciones creadas por el docente."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        projection = {
            "_id": 1,
            "encabezado.grado": 1,
            "encabezado.seccion": 1,
            "metadatos.subarea_curricular": 1,
            "metadatos.fecha_creacion": 1,
            "metadatos.estado": 1
        }

        plans = list(
            db["planificaciones_generadas"]
            .find({"id_usuario": user_obj_id}, projection)
            .sort("metadatos.fecha_creacion", -1)
            .limit(limit)
        )

        return json.dumps({"status": "success", "id_usuario": effective_id, "planificaciones_recientes": plans}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar planificaciones recientes: {str(e)}"})


@tool("get_latest_plan_instruments_and_resources", args_schema=GetLatestPlanInstrumentsAndResourcesInput)
def get_latest_plan_instruments_and_resources(config: RunnableConfig = None, id_usuario: str = "") -> str:
    """1.C (consultas_db.md): Obtiene los últimos 3 instrumentos de evaluación y los últimos 3 recursos multimodales creados para las planificaciones del usuario."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        user_plans = list(db["planificaciones_generadas"].find({"id_usuario": user_obj_id}, projection={"_id": 1}))
        if not user_plans:
            return json.dumps({
                "status": "success",
                "id_usuario": effective_id,
                "ultimos_instrumentos": [],
                "ultimos_recursos": []
            }, ensure_ascii=False)

        plan_ids = [plan["_id"] for plan in user_plans]

        instruments = list(
            db["instrumentos_evaluacion"]
            .find({"id_planificacion": {"$in": plan_ids}})
            .sort("_id", -1)
            .limit(3)
        )

        resources = list(
            db["recursos_multimodales"]
            .find({"id_planificacion": {"$in": plan_ids}})
            .sort("_id", -1)
            .limit(3)
        )

        return json.dumps({
            "status": "success",
            "id_usuario": effective_id,
            "ultimos_instrumentos": instruments,
            "ultimos_recursos": resources
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar últimos instrumentos y recursos: {str(e)}"})


@tool("get_paginated_lesson_plans", args_schema=GetPaginatedLessonPlansInput)
def get_paginated_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", page: int = 1, limit: int = 10) -> str:
    """2 (consultas_db.md): Obtiene la lista paginada de planificaciones pertenecientes al usuario con conteo total."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        total_count = db["planificaciones_generadas"].count_documents({"id_usuario": user_obj_id})
        skip = (max(1, page) - 1) * limit

        projection = {
            "_id": 1,
            "encabezado.grado": 1,
            "encabezado.seccion": 1,
            "metadatos.subarea_curricular": 1,
            "metadatos.fecha_creacion": 1,
            "metadatos.estado": 1
        }

        plans = list(
            db["planificaciones_generadas"]
            .find({"id_usuario": user_obj_id}, projection)
            .sort("metadatos.fecha_creacion", -1)
            .skip(skip)
            .limit(limit)
        )

        total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

        return json.dumps({
            "status": "success",
            "total_registros": total_count,
            "total_paginas": total_pages,
            "pagina_actual": page,
            "registros_por_pagina": limit,
            "planificaciones": plans
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error en el historial paginado: {str(e)}"})


@tool("get_full_lesson_plan_details", args_schema=GetFullLessonPlanDetailsInput)
def get_full_lesson_plan_details(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
    """3 (consultas_db.md): Recupera el documento completo de una planificación junto a sus instrumentos y recursos asociados."""
    try:
        db = get_db()
        plan_obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": plan_obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db["planificaciones_generadas"].find_one(query)
        if not plan:
            return json.dumps({"status": "error", "message": "Acceso denegado o planificación no encontrada para este usuario."})

        instruments = list(db["instrumentos_evaluacion"].find({"id_planificacion": plan_obj_id}))
        resources = list(db["recursos_multimodales"].find({"id_planificacion": plan_obj_id}))

        return json.dumps({
            "status": "success",
            "planificacion": plan,
            "instrumentos_evaluacion": instruments,
            "recursos_multimodales": resources
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar detalle completo de planificación: {str(e)}"})


@tool("get_cnb_careers_list")
def get_cnb_careers_list() -> str:
    """4.A (consultas_db.md): Recupera la lista única de nombres de carreras académicas registradas en el CNB."""
    try:
        db = get_db()
        careers = db["cnb_areas"].distinct("nombre_carrera")
        return json.dumps({"status": "success", "carreras": careers}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener catálogo de carreras: {str(e)}"})


@tool("get_cnb_areas_by_careers", args_schema=GetCNBAreasByCareersInput)
def get_cnb_areas_by_careers(carreras: List[str]) -> str:
    """4.B (consultas_db.md): Recupera las áreas curriculares pertenecientes a las carreras especificadas."""
    try:
        db = get_db()

        areas = list(db["cnb_areas"].find({"nombre_carrera": {"$in": carreras}}))
        return json.dumps({"status": "success", "areas": areas}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener áreas por carrera: {str(e)}"})


@tool("get_cnb_subareas_by_area_id", args_schema=GetCNBSubareasByAreaIdInput)
def get_cnb_subareas_by_area_id(id_area: str) -> str:
    """4.C (consultas_db.md): Recupera las subáreas pertenecientes a un área curricular específica de MongoDB."""
    try:
        db = get_db()
        area_obj_id = ObjectId(id_area.strip())
        subareas = list(db["cnb_subareas"].find({"id_area": area_obj_id}))
        return json.dumps({"status": "success", "id_area": id_area, "subareas": subareas}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener subáreas: {str(e)}"})


# ==========================================
# 9. FUNCIONES DE SERVICIO DE USUARIOS (Sin anotación @tool)
# ==========================================

def create_user_doc(data: dict) -> dict:
    """
    Función interna de servicio backend para crear un usuario en la colección 'usuarios' de MongoDB.
    Requiere google_id y datos verídicos obtenidos directamente del token de Google OAuth.
    """
    try:
        db = get_db()
        google_id = str(data.get("google_id", "")).strip()
        email = str(data.get("email", "")).strip().lower()

        if not google_id:
            return {"status": "error", "message": "El campo 'google_id' es obligatorio."}
        if not email:
            return {"status": "error", "message": "El campo 'email' es obligatorio."}

        existing = db["usuarios"].find_one({"google_id": google_id})
        if existing:
            db["usuarios"].update_one({"_id": existing["_id"]}, {"$set": {"ultimo_acceso": _get_bson_timestamp()}})
            existing["_id"] = str(existing["_id"])
            return {"status": "info", "message": "Usuario existente.", "user": existing, "id_usuario": existing["_id"]}

        user_doc = {
            "google_id": google_id,
            "nombres": str(data.get("nombres", "")),
            "apellidos": str(data.get("apellidos", "")),
            "email": email,
            "estado": str(data.get("estado", "activo")),
            "fecha_creacion": _get_bson_timestamp(),
            "ultimo_acceso": _get_bson_timestamp(),
            "foto_perfil": str(data.get("foto_perfil", "")),
            "rol": str(data.get("rol", "docente"))
        }

        res = db["usuarios"].insert_one(user_doc)
        user_doc["_id"] = str(res.inserted_id)
        return {"status": "success", "message": "Usuario creado.", "user": user_doc, "id_usuario": user_doc["_id"]}

    except Exception as e:
        return {"status": "error", "message": f"Error en creación de usuario: {str(e)}"}


def get_user_by_google_id(google_id: str) -> Optional[dict]:
    """
    Función interna de servicio backend para consultar un usuario únicamente por su 'google_id' en la colección 'usuarios'.
    """
    try:
        db = get_db()
        gid = str(google_id).strip()
        if not gid:
            return None
        user = db["usuarios"].find_one({"google_id": gid})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None


def get_user_profile_doc(id_usuario: str) -> Optional[dict]:
    """Función interna de servicio backend para obtener el perfil de un usuario por su _id de MongoDB."""
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        user = db["usuarios"].find_one({"_id": obj_id})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None


def update_user_profile_doc(id_usuario: str, update_data: dict) -> bool:
    """Función interna de servicio backend para actualizar el perfil mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        updates = _clean_updates(update_data)
        updates["ultimo_acceso"] = _get_bson_timestamp()

        res = db["usuarios"].update_one({"_id": obj_id}, {"$set": updates})
        return res.matched_count > 0
    except Exception:
        return False


def delete_user_profile_doc(id_usuario: str) -> bool:
    """Función interna de servicio backend para eliminar la cuenta de usuario."""
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        res = db["usuarios"].delete_one({"_id": obj_id})
        return res.deleted_count > 0
    except Exception:
        return False