import json
import time
from datetime import datetime
from typing import Union, Dict, Any, List, Optional
from bson import ObjectId
from bson.timestamp import Timestamp
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from core.config import get_env_variable
from core.collections import (
    AREAS,
    SUBAREAS,
    VECTORES,
    PLANIFICACION,
    EVALUACION,
    RECURSOS,
    REFRESH_TOKENS,
    USUARIOS,
)
from core.tool_inputs import (
    Subarea,
    EncabezadoPlan,
    FilaCurricularPlan,
    InstrumentoGeneradoDetail,
    MetadatosPlanInput,
    SaveCurricularStructureInput,
    SaveLessonPlanInput,
    SaveAssessmentInstrumentInput,
    SaveMultimodalResourceInput,
    UpdateLessonPlanInput,
    UpdateAssessmentInstrumentInput,
    UpdateMultimodalResourceInput,
)


def _get_bson_timestamp() -> Timestamp:
    """Genera un objeto BSON Timestamp de MongoDB."""
    return Timestamp(int(time.time()), 1)


def get_mongo_client(timeout_ms: Optional[int] = None) -> MongoClient:
    """Retorna una instancia de MongoClient utilizando la URI configurada en MONGODB_URI."""
    mongodb_uri = get_env_variable("MONGODB_URI")
    if timeout_ms:
        return MongoClient(mongodb_uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
    return MongoClient(mongodb_uri)


def get_db():
    """Retorna la base de datos de MongoDB a partir de DB_NAME."""
    client = get_mongo_client()
    db_name = get_env_variable("DB_NAME")
    return client[db_name]


def check_db_connection(timeout_ms: int = 2000) -> bool:
    """
    Verifica si la comunicación con la base de datos MongoDB está activa.
    Envía un comando 'ping' con un tiempo máximo de espera (timeout).

    Args:
        timeout_ms (int): Tiempo de espera en milisegundos para la verificación.

    Returns:
        bool: True si la base de datos está conectada y responde, False en caso de falla.
    """
    try:
        client = get_mongo_client(timeout_ms=timeout_ms)
        client.admin.command("ping")
        return True
    except Exception:
        return False


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


def extract_teacher_name_from_config(config: Optional[Any] = None, user_id: str = "") -> str:
    """
    Extrae el nombre del docente autenticado del objeto RunnableConfig de LangGraph
    o lo consulta directamente del perfil en MongoDB.
    """
    if config:
        configurable = {}
        if isinstance(config, dict):
            configurable = config.get("configurable", {})
        elif hasattr(config, "configurable"):
            configurable = getattr(config, "configurable", {})
        elif hasattr(config, "get"):
            configurable = config.get("configurable", {})

        auth_user = configurable.get("langgraph_auth_user")
        if isinstance(auth_user, dict):
            nombres = auth_user.get("nombres") or auth_user.get("name")
            if nombres:
                return str(nombres).strip()
        elif hasattr(auth_user, "nombres"):
            return str(getattr(auth_user, "nombres")).strip()

        nombre_docente = configurable.get("nombre_docente")
        if nombre_docente:
            return str(nombre_docente).strip()

    effective_id = extract_user_id_from_config(config) or user_id
    if effective_id and len(effective_id.strip()) == 24:
        try:
            db = get_db()
            user_doc = db[USUARIOS].find_one({"_id": ObjectId(effective_id.strip())})
            if user_doc:
                nombres = str(user_doc.get("nombres", "")).strip()
                apellidos = str(user_doc.get("apellidos", "")).strip()
                full_name = f"{nombres} {apellidos}".strip()
                if full_name:
                    return full_name
        except Exception:
            pass

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
    nombre_carrera = data.get("nombre_carrera")
    nombre_area = data.get("nombre_area")

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

    res = db[AREAS].insert_one(area_doc)
    return res.inserted_id


def insert_cnb_subarea_doc(data: dict) -> ObjectId:
    """Función interna individual para insertar una subárea curricular en 'cnb_subareas'."""
    db = get_db()
    id_area = data.get("id_area")
    if isinstance(id_area, str):
        id_area = ObjectId(id_area)

    subarea_doc = {
        "id_area": id_area,
        "nombre_subarea": data.get("nombre_subarea"),
        "competencias": data.get("competencias", [])
    }

    res = db[SUBAREAS].insert_one(subarea_doc)
    return res.inserted_id


def insert_cnb_vector_doc(data: dict) -> ObjectId:
    """Función interna individual para insertar un nodo en 'cnb_vectores'."""
    db = get_db()
    id_subarea = data.get("id_subarea_relacionada")
    if isinstance(id_subarea, str):
        id_subarea = ObjectId(id_subarea)

    doc = {
        "id_subarea_relacionada": id_subarea,
        "nombre_subarea": data.get("nombre_subarea"),
        "tipo_nodo": data.get("tipo_nodo", "competencia"),
        "referencia_jerarquica": data.get("referencia_jerarquica", []),
        "texto_a_buscar": data.get("texto_a_buscar", ""),
        "vector_embedding": data.get("vector_embedding", []),
        "vector_estado": data.get("vector_estado", False)
    }

    res = db[VECTORES].insert_one(doc)
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
        }

        area_id = insert_cnb_area_doc(area_data)

        subareas_inserted = []
        vectores_nodes_created = 0

        for sub in subareas_dicts:
            nombre_subarea = sub.get("nombre_subarea")
            competencias = sub.get("competencias", [])

            subarea_data = {
                "id_area": area_id,
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
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    """
    CRUD Create: Guarda/crea una nueva planificación docente en 'planificaciones_generadas'.
    """
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        user_obj_id = _ensure_object_id(effective_id) if effective_id else ObjectId()

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

        teacher_name = extract_teacher_name_from_config(config, effective_id) or "Docente"

        doc = {
            "id_usuario": user_obj_id,
            "metadatos": metadatos_doc,
            "encabezado": {
                "centro_educativo": str(enc_dict.get("centro_educativo", "")),
                "lugar": str(enc_dict.get("lugar", "")),
                "grado": str(enc_dict.get("grado", "")),
                "seccion": str(enc_dict.get("seccion", "")),
                "nombre_docente": teacher_name,
                "duracion": str(enc_dict.get("duracion", "1 día")),
                "cantidad_periodos": int(enc_dict.get("cantidad_periodos", 1)),
                "duracion_periodos": int(enc_dict.get("duracion_periodos", 40))
            },
            "desarrollo_curricular": formatted_desarrollo
        }

        res = db[PLANIFICACION].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Planificación de clase creada exitosamente.",
            "id_planificacion": str(res.inserted_id),
            "id_usuario": str(user_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al crear planificación: {str(e)}"})


@tool("get_planification_by_id")
def get_planification_by_id(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
    """CRUD Read & Privacidad: Busca y recupera una planificación docente por su ID en MongoDB."""
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())
        
        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[PLANIFICACION].find_one(query)
        if not plan:
            return json.dumps({
                "status": "error",
                "message": f"Acceso denegado o planificación con _id '{id_planificacion}' no encontrada para este usuario."
            }, ensure_ascii=False)

        return json.dumps({"status": "success", "planificacion": plan}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar planificación: {str(e)}"})


@tool("update_lesson_plan", args_schema=UpdateLessonPlanInput)
def update_lesson_plan(
    id_planificacion: str,
    metadatos: Optional[Union[dict, MetadatosPlanInput]] = None,
    encabezado: Optional[Union[dict, EncabezadoPlan]] = None,
    desarrollo_curricular: Optional[List[Union[dict, FilaCurricularPlan]]] = None,
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    """CRUD Update & Privacidad: Actualiza los campos solicitados mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        merged_updates = {}
        if metadatos is not None:
            merged_updates["metadatos"] = _to_dict(metadatos)
        if encabezado is not None:
            merged_updates["encabezado"] = _to_dict(encabezado)
        if desarrollo_curricular is not None:
            des_list = []
            for item in desarrollo_curricular:
                des_list.append(_to_dict(item))
            merged_updates["desarrollo_curricular"] = des_list

        updates = _clean_updates(merged_updates)
        if "id_usuario" in updates:
            del updates["id_usuario"]

        if not updates:
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        res = db[PLANIFICACION].update_one(query, {"$set": updates})

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


@tool("delete_lesson_plan")
def delete_lesson_plan(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "", confirm: bool = True) -> str:
    """CRUD Delete & Privacidad: Elimina una planificación por su ID en MongoDB validando propiedad y confirmación."""
    try:
        if not confirm:
            return json.dumps({
                "status": "pending_confirmation",
                "message": f"CONFIRMACIÓN REQUERIDA: ¿Está seguro de eliminar permanentemente la planificación '{id_planificacion}'?"
            }, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        res = db[PLANIFICACION].delete_one(query)

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
# 3. ÁREAS CURRICULARES (cnb_areas)
# ==========================================

@tool("get_cnb_area_by_id")
def get_cnb_area_by_id(id_area: str) -> str:
    """CRUD Read: Busca un área curricular del CNB por su ID de MongoDB."""
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        area = db[AREAS].find_one({"_id": obj_id})
        if not area:
            return json.dumps({"status": "error", "message": f"Área curricular con _id '{id_area}' no encontrada."})
        return json.dumps({"status": "success", "area": area}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer área curricular: {str(e)}"})

# ==========================================
# 4. SUBÁREAS CURRICULARES (cnb_subareas)
# ==========================================

@tool("get_cnb_subarea_by_id")
def get_cnb_subarea_by_id(id_subarea: str) -> str:
    """CRUD Read: Busca una subárea curricular por su ID de MongoDB en 'cnb_subareas'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        sub = db[SUBAREAS].find_one({"_id": obj_id})
        if not sub:
            return json.dumps({"status": "error", "message": f"Subárea '{id_subarea}' no encontrada."})
        return json.dumps({"status": "success", "subarea": sub}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer subárea: {str(e)}"})

# ==========================================
# 5. VECTORES DE BÚSQUEDA (cnb_vectores)
# ==========================================

def get_cnb_vector_by_id(id_vector: str) -> str:
    """CRUD Read: Obtiene un nodo vectorial de 'cnb_vectores' por su _id."""
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        vec = db[VECTORES].find_one({"_id": obj_id})
        if not vec:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})
        return json.dumps({"status": "success", "vector": vec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer vector: {str(e)}"})


def update_cnb_vector(id_vector: str, update_data: Dict[str, Any]) -> str:
    """CRUD Update: Actualiza los campos de un registro en 'cnb_vectores' mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        updates = _clean_updates(update_data)

        res = db[VECTORES].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar vector: {str(e)}"})


def delete_cnb_vector(id_vector: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un registro vectorial en 'cnb_vectores' por su _id tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar vector '{id_vector}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        res = db[VECTORES].delete_one({"_id": obj_id})
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
    id_fila: int,
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
            "id_fila": int(id_fila),
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "instrumento_generado": inst_gen_dict
        }

        res = db[EVALUACION].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Instrumento de evaluación guardado exitosamente.",
            "id_instrumento": str(res.inserted_id),
            "id_planificacion": str(plan_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el instrumento de evaluación: {str(e)}"})


@tool("get_assessment_instrument_by_id")
def get_assessment_instrument_by_id(id_instrumento: str) -> str:
    """CRUD Read: Obtiene un instrumento de evaluación por su ID de MongoDB en 'instrumentos_evaluacion'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        inst = db[EVALUACION].find_one({"_id": obj_id})
        if not inst:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})
        return json.dumps({"status": "success", "instrumento": inst}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar instrumento de evaluación: {str(e)}"})


@tool("update_assessment_instrument", args_schema=UpdateAssessmentInstrumentInput)
def update_assessment_instrument(
    id_instrumento: str,
    id_fila: Optional[int] = None,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    instrumento_generado: Optional[Union[dict, InstrumentoGeneradoDetail]] = None
) -> str:
    """CRUD Update: Actualiza los datos específicos de un instrumento de evaluación mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())

        merged_updates = {}
        if id_fila is not None:
            merged_updates["id_fila"] = int(id_fila)
        if id_actividad is not None:
            merged_updates["id_actividad"] = _ensure_object_id(id_actividad)
        if tipo is not None:
            merged_updates["tipo"] = str(tipo)
        if titulo is not None:
            merged_updates["titulo"] = str(titulo)
        if instrumento_generado is not None:
            merged_updates["instrumento_generado"] = _to_dict(instrumento_generado)

        updates = _clean_updates(merged_updates)
        if "id_planificacion" in updates:
            del updates["id_planificacion"]

        if not updates:
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        res = db[EVALUACION].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Instrumento '{id_instrumento}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar instrumento de evaluación: {str(e)}"})


@tool("delete_assessment_instrument")
def delete_assessment_instrument(id_instrumento: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un instrumento de evaluación por su ID tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar instrumento '{id_instrumento}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        res = db[EVALUACION].delete_one({"_id": obj_id})
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
    id_fila: int,
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
            "id_fila": int(id_fila),
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "url": str(url)
        }

        res = db[RECURSOS].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Recurso multimodal guardado exitosamente.",
            "id_recurso": str(res.inserted_id),
            "id_planificacion": str(plan_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el recurso multimodal: {str(e)}"})


@tool("get_multimodal_resource_by_id")
def get_multimodal_resource_by_id(id_recurso: str) -> str:
    """CRUD Read: Obtiene un recurso multimodal por su ID de MongoDB en 'recursos_multimodales'."""
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        rec = db[RECURSOS].find_one({"_id": obj_id})
        if not rec:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})
        return json.dumps({"status": "success", "recurso": rec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al leer recurso multimodal: {str(e)}"})


@tool("update_multimodal_resource", args_schema=UpdateMultimodalResourceInput)
def update_multimodal_resource(
    id_recurso: str,
    id_fila: Optional[int] = None,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    url: Optional[str] = None
) -> str:
    """CRUD Update: Actualiza campos específicos de un recurso multimodal mediante $set."""
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())

        merged_updates = {}
        if id_fila is not None:
            merged_updates["id_fila"] = int(id_fila)
        if id_actividad is not None:
            merged_updates["id_actividad"] = _ensure_object_id(id_actividad)
        if tipo is not None:
            merged_updates["tipo"] = str(tipo)
        if titulo is not None:
            merged_updates["titulo"] = str(titulo)
        if url is not None:
            merged_updates["url"] = str(url)

        updates = _clean_updates(merged_updates)
        if "id_planificacion" in updates:
            del updates["id_planificacion"]

        if not updates:
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        res = db[RECURSOS].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Recurso '{id_recurso}' actualizado exitosamente mediante $set."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar recurso multimodal: {str(e)}"})


@tool("delete_multimodal_resource")
def delete_multimodal_resource(id_recurso: str, confirm: bool = True) -> str:
    """CRUD Delete: Elimina un recurso multimodal por su ID en 'recursos_multimodales' tras confirmación."""
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMACIÓN REQUERIDA: ¿Eliminar recurso '{id_recurso}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        res = db[RECURSOS].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Recurso '{id_recurso}' eliminado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar recurso multimodal: {str(e)}"})


# ==========================================
# 8. HERRAMIENTAS DE CONSULTA Y SEGURIDAD
# ==========================================

@tool("get_top_frequent_courses")
def get_top_frequent_courses(config: RunnableConfig = None, id_usuario: str = "", limit: int = 4) -> str:
    """Agrupa las planificaciones del usuario por subárea curricular y obtiene las más frecuentes."""
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

        results = list(db[PLANIFICACION].aggregate(pipeline))
        return json.dumps({"status": "success", "id_usuario": effective_id, "top_cursos": results}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar top cursos: {str(e)}"})


@tool("get_recent_lesson_plans")
def get_recent_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", limit: int = 3) -> str:
    """Recupera los datos del encabezado y metadatos de las últimas planificaciones creadas por el docente."""
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
            db[PLANIFICACION]
            .find({"id_usuario": user_obj_id}, projection)
            .sort("metadatos.fecha_creacion", -1)
            .limit(limit)
        )

        return json.dumps({"status": "success", "id_usuario": effective_id, "planificaciones_recientes": plans}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar planificaciones recientes: {str(e)}"})


@tool("get_latest_plan_instruments_and_resources")
def get_latest_plan_instruments_and_resources(config: RunnableConfig = None, id_usuario: str = "") -> str:
    """Obtiene los últimos 3 instrumentos de evaluación y los últimos 3 recursos multimodales creados para las planificaciones del usuario."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        user_plans = list(db[PLANIFICACION].find({"id_usuario": user_obj_id}, projection={"_id": 1}))
        if not user_plans:
            return json.dumps({
                "status": "success",
                "id_usuario": effective_id,
                "ultimos_instrumentos": [],
                "ultimos_recursos": []
            }, ensure_ascii=False)

        plan_ids = [plan["_id"] for plan in user_plans]

        instruments = list(
            db[EVALUACION]
            .find({"id_planificacion": {"$in": plan_ids}})
            .sort("_id", -1)
            .limit(3)
        )

        resources = list(
            db[RECURSOS]
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


@tool("get_paginated_lesson_plans")
def get_paginated_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", page: int = 1, limit: int = 10) -> str:
    """Obtiene la lista paginada de planificaciones pertenecientes al usuario con conteo total."""
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Identificador de usuario autenticado no proporcionado o inválido."})

        user_obj_id = ObjectId(effective_id.strip())

        total_count = db[PLANIFICACION].count_documents({"id_usuario": user_obj_id})
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
            db[PLANIFICACION]
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


@tool("get_lesson_plan_details")
def get_lesson_plan_details(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
    """Recupera el documento completo de una planificación junto a sus instrumentos y recursos asociados."""
    try:
        db = get_db()
        plan_obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": plan_obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[PLANIFICACION].find_one(query)
        if not plan:
            return json.dumps({"status": "error", "message": "Acceso denegado o planificación no encontrada para este usuario."})

        instruments = list(db[EVALUACION].find({"id_planificacion": plan_obj_id}))
        resources = list(db[RECURSOS].find({"id_planificacion": plan_obj_id}))

        return json.dumps({
            "status": "success",
            "planificacion": plan,
            "instrumentos_evaluacion": instruments,
            "recursos_multimodales": resources
        }, cls=JSONEncoderCustom, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al consultar detalle completo de planificación: {str(e)}"})


@tool("get_cnb_careers_list")
def get_cnb_careers_list() -> str:
    """Recupera la lista única de nombres de carreras académicas registradas en el CNB."""
    try:
        db = get_db()
        raw_careers = db[AREAS].distinct("nombre_carrera")
        career_names = [str(c).strip() for c in raw_careers if c and str(c).strip()]
        return json.dumps({"status": "success", "carreras": career_names}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener catálogo de carreras: {str(e)}"})


@tool("get_cnb_areas_by_career")
def get_cnb_areas_by_career(carrera: str, page: int = 1, limit: int = 10) -> str:
    """Recupera la lista paginada de áreas curriculares (id y nombre_area) pertenecientes a una carrera específica del CNB."""
    try:
        db = get_db()
        query = {"nombre_carrera": carrera.strip()}
        total_count = db[AREAS].count_documents(query)
        skip = (max(1, page) - 1) * limit

        projection = {
            "_id": 1,
            "nombre_area": 1
        }

        areas_cursor = db[AREAS].find(query, projection).skip(skip).limit(limit)
        areas = []
        for doc in areas_cursor:
            areas.append({
                "id_area": str(doc["_id"]),
                "nombre_area": doc.get("nombre_area", "")
            })

        total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

        return json.dumps({
            "status": "success",
            "carrera": carrera,
            "total_registros": total_count,
            "total_paginas": total_pages,
            "pagina_actual": page,
            "registros_por_pagina": limit,
            "areas": areas
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener áreas por carrera: {str(e)}"})
        

@tool("get_cnb_subareas_by_area_id")
def get_cnb_subareas_by_area_id(id_area: str, page: int = 1, limit: int = 10) -> str:
    """Recupera la lista paginada de subáreas curriculares (id y nombre_subarea) pertenecientes a un área en 'cnb_subareas'."""
    try:
        db = get_db()
        area_obj_id = ObjectId(id_area.strip())
        query = {"id_area": area_obj_id}
        total_count = db[SUBAREAS].count_documents(query)
        skip = (max(1, page) - 1) * limit

        projection = {
            "_id": 1,
            "nombre_subarea": 1
        }

        subareas_cursor = db[SUBAREAS].find(query, projection).skip(skip).limit(limit)
        subareas = []
        for doc in subareas_cursor:
            subareas.append({
                "id_subarea": str(doc["_id"]),
                "nombre_subarea": doc.get("nombre_subarea", "")
            })

        total_pages = (total_count + limit - 1) // limit if limit > 0 else 0

        return json.dumps({
            "status": "success",
            "id_area": id_area,
            "total_registros": total_count,
            "total_paginas": total_pages,
            "pagina_actual": page,
            "registros_por_pagina": limit,
            "subareas": subareas
        }, ensure_ascii=False)
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

        existing = db[USUARIOS].find_one({"google_id": google_id})
        if existing:
            db[USUARIOS].update_one({"_id": existing["_id"]}, {"$set": {"ultimo_acceso": _get_bson_timestamp()}})
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

        res = db[USUARIOS].insert_one(user_doc)
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
        user = db[USUARIOS].find_one({"google_id": gid})
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
        user = db[USUARIOS].find_one({"_id": obj_id})
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

        res = db[USUARIOS].update_one({"_id": obj_id}, {"$set": updates})
        return res.matched_count > 0
    except Exception:
        return False


def delete_user_profile_doc(id_usuario: str) -> bool:
    """Función interna de servicio backend para eliminar la cuenta de usuario."""
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        res = db[USUARIOS].delete_one({"_id": obj_id})
        return res.deleted_count > 0
    except Exception:
        return False


def save_refresh_token(id_usuario: str, refresh_token: str, expires_in_days: int = 7) -> bool:
    """
    Guarda o actualiza un refresh token para el usuario en la colección 'refresh_tokens'.
    Duración por defecto: 7 días.
    """
    try:
        db = get_db()
        user_obj_id = _ensure_object_id(id_usuario)
        now = time.time()
        expires_at_epoch = now + (expires_in_days * 86400)
        doc = {
            "id_usuario": user_obj_id,
            "refresh_token": str(refresh_token).strip(),
            "fecha_creacion": _get_bson_timestamp(),
            "fecha_expiracion": Timestamp(int(expires_at_epoch), 1)
        }
        db[REFRESH_TOKENS].update_one(
            {"id_usuario": user_obj_id},
            {"$set": doc},
            upsert=True
        )
        return True
    except Exception:
        return False


def get_refresh_token_doc(refresh_token: str) -> Optional[dict]:
    """
    Busca y retorna el documento de un refresh token activo si no ha expirado.
    """
    try:
        db = get_db()
        token_str = str(refresh_token).strip()
        if not token_str:
            return None
        doc = db[REFRESH_TOKENS].find_one({"refresh_token": token_str})
        if not doc:
            return None
        now = time.time()
        exp = doc.get("fecha_expiracion")
        if not exp or not hasattr(exp, "time"):
            return None
        exp_time = exp.time
        if exp_time < now:
            db[REFRESH_TOKENS].delete_one({"_id": doc["_id"]})
            return None
        doc["_id"] = str(doc["_id"])
        if "id_usuario" in doc:
            doc["id_usuario"] = str(doc["id_usuario"])
        return doc
    except Exception:
        return None