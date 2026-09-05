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
    SUB_AREAS,
    VECTORS,
    LESSON_PLANS,
    ASSESSMENT_INSTRUMENTS,
    MULTIMODAL_RESOURCES,
    REFRESH_TOKENS,
    USERS,
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
    """
    Generates a MongoDB BSON Timestamp object.

    Returns:
        Timestamp: Current BSON timestamp.
    """
    return Timestamp(int(time.time()), 1)


def get_mongo_client(timeout_ms: Optional[int] = None) -> MongoClient:
    """
    Creates a MongoClient instance using the configured connection URI.

    Args:
        timeout_ms (int, optional): Maximum timeout in milliseconds.

    Returns:
        MongoClient: Configured MongoDB client instance.
    """
    mongodb_uri = get_env_variable("MONGODB_URI")
    if timeout_ms:
        return MongoClient(mongodb_uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
    return MongoClient(mongodb_uri)


def get_db():
    """
    Obtains the MongoDB database instance.

    Returns:
        Database: Application database instance.
    """
    client = get_mongo_client()
    db_name = get_env_variable("DB_NAME")
    return client[db_name]


def check_db_connection(timeout_ms: int = 2000) -> bool:
    """
    Verifies active connectivity with the MongoDB database.

    Args:
        timeout_ms (int, optional): Timeout limit in milliseconds. Defaults to 2000.

    Returns:
        bool: True if the database responds to ping, False otherwise.
    """
    try:
        client = get_mongo_client(timeout_ms=timeout_ms)
        client.admin.command("ping")
        return True
    except Exception:
        return False


def extract_user_id_from_config(config: Optional[Any] = None) -> str:
    """
    Extracts the user identifier from the LangGraph execution configuration.

    Args:
        config (optional): RunnableConfig object or configuration dictionary.

    Returns:
        str: Extracted user ID or empty string if not found.
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

    return str(configurable.get("id_usuario", ""))


def extract_teacher_name_from_config(config: Optional[Any] = None, user_id: str = "") -> str:
    """
    Obtains the authenticated teacher's full name from configuration or user ID.

    Args:
        config (optional): RunnableConfig object or configuration dictionary.
        user_id (str, optional): User identifier.

    Returns:
        str: Teacher name or 'Docente' by default.
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
            display_name = auth_user.get("display_name") or auth_user.get("name")
            if display_name:
                return str(display_name)

    effective_id = user_id or extract_user_id_from_config(config)
    if effective_id and len(effective_id.strip()) == 24:
        try:
            db = get_db()
            user_doc = db[USERS].find_one({"_id": ObjectId(effective_id.strip())})
            if user_doc:
                nombres = str(user_doc.get("nombres", "")).strip()
                apellidos = str(user_doc.get("apellidos", "")).strip()
                full_name = f"{nombres} {apellidos}".strip()
                if full_name:
                    return full_name
        except Exception:
            pass

    return "Docente"


class JSONEncoderCustom(json.JSONEncoder):
    """
    Custom JSON encoder for MongoDB ObjectId, Timestamp, and datetime objects.
    """
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, Timestamp):
            return o.time
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _to_dict(obj: Any) -> dict:
    """
    Converts a Pydantic model or dictionary object into a standard Python dictionary.

    Args:
        obj (Any): Pydantic BaseModel instance or dictionary.

    Returns:
        dict: Resulting Python dictionary.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def _ensure_object_id(val: Any) -> ObjectId:
    """
    Converts an input value into a MongoDB ObjectId.

    Args:
        val (Any): 24-character hex string or existing ObjectId.

    Returns:
        ObjectId: ObjectId instance.
    """
    if isinstance(val, ObjectId):
        return val
    val_str = str(val).strip()
    if len(val_str) == 24:
        return ObjectId(val_str)
    return ObjectId()


def _clean_updates(updates: dict) -> dict:
    """
    Cleans an update dictionary omitting uneditable fields and null identifiers.

    Args:
        updates (dict): Dictionary of fields to update.

    Returns:
        dict: Cleaned update dictionary.
    """
    clean = {}
    for k, v in updates.items():
        if k in ["_id", "fecha_creacion"]:
            continue
        if v is not None:
            if k in ["id_planificacion", "id_actividad", "id_subarea", "id_area", "id_usuario"] and isinstance(v, str):
                if len(v.strip()) == 24:
                    clean[k] = ObjectId(v.strip())
                else:
                    clean[k] = v
            else:
                clean[k] = v
    return clean


def insert_cnb_area_doc(data: dict) -> ObjectId:
    """
    Inserts a new curricular area document.

    Args:
        data (dict): Curricular area information dictionary.

    Returns:
        ObjectId: Inserted document identifier.
    """
    db = get_db()
    carrera = str(data.get("nombre_carrera", "")).strip()

    def _format_items(items):
        if not isinstance(items, list):
            return []
        cleaned = []
        for item in items:
            s_item = str(item).strip()
            if s_item:
                cleaned.append(s_item)
        return cleaned

    doc = {
        "nombre_carrera": carrera,
        "nombre_area": str(data.get("nombre_area", "")).strip(),
        "competencias_area": _format_items(data.get("competencias_area")),
        "actividades_sugeridas": _format_items(data.get("actividades_sugeridas")),
        "criterios_evaluacion": _format_items(data.get("criterios_evaluacion_sugeridos")),
        "fecha_creacion": _get_bson_timestamp()
    }
    res = db[AREAS].insert_one(doc)
    return res.inserted_id


def insert_cnb_subarea_doc(data: dict) -> ObjectId:
    """
    Inserts a curricular subarea into the database.

    Args:
        data (dict): Curricular subarea information dictionary.

    Returns:
        ObjectId: Inserted document identifier.
    """
    db = get_db()
    doc = {
        "id_area": _ensure_object_id(data.get("id_area")),
        "nombre_subarea": str(data.get("nombre_subarea", "")).strip(),
        "competencias": data.get("competencias", []),
        "fecha_creacion": _get_bson_timestamp()
    }
    res = db[SUB_AREAS].insert_one(doc)
    return res.inserted_id


def insert_cnb_vector_doc(data: dict) -> ObjectId:
    """
    Inserts a node for vector indexing.

    Args:
        data (dict): Vector node information.

    Returns:
        ObjectId: Inserted document identifier.
    """
    db = get_db()
    doc = {
        "id_subarea_relacionada": _ensure_object_id(data.get("id_subarea_relacionada")),
        "nombre_subarea": str(data.get("nombre_subarea", "")).strip(),
        "tipo_nodo": str(data.get("tipo_nodo", "")).strip(),
        "referencia_jerarquica": data.get("referencia_jerarquica", []),
        "texto_a_buscar": str(data.get("texto_a_buscar", "")).strip(),
        "vector_embedding": data.get("vector_embedding", []),
        "vector_estado": bool(data.get("vector_estado", False)),
        "fecha_creacion": _get_bson_timestamp()
    }
    res = db[VECTORS].insert_one(doc)
    return res.inserted_id


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
    Saves the CNB curricular structure with its areas and subareas.

    Args:
        nombre_carrera (str): Official career name.
        nombre_area (str): Curricular area name.
        competencias_area (List[str]): Area competencies.
        actividades_sugeridas (List[str]): Suggested area activities.
        criterios_evaluacion_sugeridos (List[str]): Suggested evaluation criteria.
        subareas (List[Union[dict, Subarea]]): Subareas belonging to the area.

    Returns:
        str: JSON formatted response with operation status and created area ID.
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
            "message": "Curricular structure saved successfully.",
            "id_area": str(area_id),
            "subareas_insertadas": subareas_inserted,
            "nodos_vectoriales_creados": vectores_nodes_created
        }
        return json.dumps(response, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving curricular structure: {str(e)}"})


@tool("save_lesson_plan", args_schema=SaveLessonPlanInput)
def save_lesson_plan(
    metadatos: Union[dict, MetadatosPlanInput],
    encabezado: Union[dict, EncabezadoPlan],
    desarrollo_curricular: List[Union[dict, FilaCurricularPlan]],
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    """
    Saves a teacher's lesson plan in the database.

    Args:
        metadatos (Union[dict, MetadatosPlanInput]): Metadata of the lesson plan.
        encabezado (Union[dict, EncabezadoPlan]): General header data.
        desarrollo_curricular (List[Union[dict, FilaCurricularPlan]]): Curricular development rows.
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.

    Returns:
        str: JSON formatted response with the saved lesson plan ID.
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

        res = db[LESSON_PLANS].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Teacher lesson plan created successfully.",
            "id_planificacion": str(res.inserted_id),
            "id_usuario": str(user_obj_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error creating lesson plan: {str(e)}"})


@tool("get_planification_by_id")
def get_planification_by_id(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
    """
    Retrieves a teacher's lesson plan by its identifier.

    Args:
        id_planificacion (str): Unique lesson plan identifier.
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.

    Returns:
        str: JSON formatted response with details of the retrieved lesson plan.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[LESSON_PLANS].find_one(query)
        if not plan:
            return json.dumps({"status": "error", "message": f"Access denied or lesson plan '{id_planificacion}' not found."})

        return json.dumps({"status": "success", "planificacion": plan}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving lesson plan: {str(e)}"})


@tool("get_learning_activity_by_id")
def get_learning_activity_by_id(id_actividad: str) -> str:
    """
    Retrieves a specific learning activity by its identifier using pipeline destructuring.

    Args:
        id_actividad (str): Unique learning activity identifier.

    Returns:
        str: JSON formatted response with destructured learning activity data.
    """
    try:
        db = get_db()
        act_obj_id = ObjectId(id_actividad.strip())

        pipeline = [
            {"$unwind": "$desarrollo_curricular"},
            {"$unwind": "$desarrollo_curricular.actividades_aprendizaje"},
            {"$match": {"desarrollo_curricular.actividades_aprendizaje.id_actividad": act_obj_id}},
            {"$project": {
                "_id": 0,
                "id_actividad": "$desarrollo_curricular.actividades_aprendizaje.id_actividad",
                "fase": "$desarrollo_curricular.actividades_aprendizaje.fase",
                "descripcion": "$desarrollo_curricular.actividades_aprendizaje.descripcion"
            }}
        ]

        results = list(db[LESSON_PLANS].aggregate(pipeline))
        if not results:
            return json.dumps({"status": "error", "message": f"Learning activity '{id_actividad}' not found."})

        return json.dumps({"status": "success", "actividad": results[0]}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving learning activity: {str(e)}"})


@tool("update_lesson_plan", args_schema=UpdateLessonPlanInput)
def update_lesson_plan(
    id_planificacion: str,
    metadatos: Optional[Union[dict, MetadatosPlanInput]] = None,
    encabezado: Optional[Union[dict, EncabezadoPlan]] = None,
    desarrollo_curricular: Optional[List[Union[dict, FilaCurricularPlan]]] = None,
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    """
    Updates specified fields of an existing teacher's lesson plan.

    Args:
        id_planificacion (str): Unique identifier of the lesson plan to update.
        metadatos (Union[dict, MetadatosPlanInput], optional): Updated metadata.
        encabezado (Union[dict, EncabezadoPlan], optional): Updated header data.
        desarrollo_curricular (List[Union[dict, FilaCurricularPlan]], optional): Updated curricular development.
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.

    Returns:
        str: JSON formatted response with the update execution status.
    """
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
            return json.dumps({"status": "error", "message": "No valid fields provided for update."})

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        res = db[LESSON_PLANS].update_one(query, {"$set": updates})

        if res.matched_count == 0:
            return json.dumps({
                "status": "error",
                "message": f"Access denied or lesson plan '{id_planificacion}' not found."
            }, ensure_ascii=False)

        return json.dumps({
            "status": "success",
            "message": f"Lesson plan '{id_planificacion}' successfully updated.",
            "modified_count": res.modified_count
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error updating lesson plan: {str(e)}"})


@tool("delete_lesson_plan")
def delete_lesson_plan(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "", confirm: bool = True) -> str:
    """
    Deletes a teacher's lesson plan by its identifier.

    Args:
        id_planificacion (str): Unique identifier of the lesson plan to delete.
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.
        confirm (bool, optional): Prior confirmation required for deletion. Defaults to True.

    Returns:
        str: JSON formatted response with deletion status.
    """
    try:
        if not confirm:
            return json.dumps({
                "status": "pending_confirmation",
                "message": f"CONFIRMATION REQUIRED: Are you sure you want to delete lesson plan '{id_planificacion}'?"
            }, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[LESSON_PLANS].find_one(query)
        if not plan:
            return json.dumps({
                "status": "error",
                "message": f"Access denied or lesson plan '{id_planificacion}' not found to delete."
            }, ensure_ascii=False)

        activity_ids = []
        for fila in plan.get("desarrollo_curricular", []):
            for act in fila.get("actividades_aprendizaje", []):
                act_id = act.get("id_actividad")
                if act_id:
                    activity_ids.append(_ensure_object_id(act_id))

        res = db[LESSON_PLANS].delete_one({"_id": obj_id})

        if activity_ids:
            db[ASSESSMENT_INSTRUMENTS].delete_many({"id_actividad": {"$in": activity_ids}})
            db[MULTIMODAL_RESOURCES].delete_many({"id_actividad": {"$in": activity_ids}})

        return json.dumps({
            "status": "success",
            "message": f"Lesson plan '{id_planificacion}' and associated instruments/resources successfully deleted."
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error deleting lesson plan: {str(e)}"})


@tool("get_cnb_area_by_id")
def get_cnb_area_by_id(id_area: str) -> str:
    """
    Retrieves curricular area data by its identifier.

    Args:
        id_area (str): Curricular area identifier.

    Returns:
        str: JSON formatted response with curricular area information.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        area = db[AREAS].find_one({"_id": obj_id})
        if not area:
            return json.dumps({"status": "error", "message": f"Curricular area '{id_area}' not found."})
        return json.dumps({"status": "success", "area": area}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving curricular area: {str(e)}"})


@tool("get_cnb_subarea_by_id")
def get_cnb_subarea_by_id(id_subarea: str) -> str:
    """
    Retrieves curricular subarea data by its identifier.

    Args:
        id_subarea (str): Curricular subarea identifier.

    Returns:
        str: JSON formatted response with curricular subarea information.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        subarea = db[SUB_AREAS].find_one({"_id": obj_id})
        if not subarea:
            return json.dumps({"status": "error", "message": f"Curricular subarea '{id_subarea}' not found."})
        return json.dumps({"status": "success", "subarea": subarea}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving curricular subarea: {str(e)}"})


@tool("get_cnb_vector_by_id")
def get_cnb_vector_by_id(id_vector: str) -> str:
    """
    Retrieves a vector indexing node by its identifier.

    Args:
        id_vector (str): Vector node identifier.

    Returns:
        str: JSON formatted response with vector node information.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        vec = db[VECTORS].find_one({"_id": obj_id})
        if not vec:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' not found."})
        return json.dumps({"status": "success", "vector": vec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving vector record: {str(e)}"})


def update_cnb_vector(id_vector: str, update_data: Dict[str, Any]) -> str:
    """
    Updates information for an existing vector node.

    Args:
        id_vector (str): Identifier of the vector node to update.
        update_data (Dict[str, Any]): Update fields dictionary.

    Returns:
        str: JSON formatted response with update execution status.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        updates = _clean_updates(update_data)

        res = db[VECTORS].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' not found."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' successfully updated."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error updating vector record: {str(e)}"})


def delete_cnb_vector(id_vector: str, confirm: bool = True) -> str:
    """
    Deletes a vector node by its identifier.

    Args:
        id_vector (str): Identifier of the node to delete.
        confirm (bool, optional): Prior confirmation required for deletion. Defaults to True.

    Returns:
        str: JSON formatted response with deletion result.
    """
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMATION REQUIRED: Delete vector '{id_vector}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        res = db[VECTORS].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' not found."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' successfully deleted."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error deleting vector record: {str(e)}"})


@tool("save_assessment_instrument", args_schema=SaveAssessmentInstrumentInput)
def save_assessment_instrument(
    id_actividad: str,
    tipo: str,
    titulo: str,
    instrumento_generado: Union[dict, InstrumentoGeneradoDetail]
) -> str:
    """
    Saves an assessment instrument linked to a learning activity.

    Args:
        id_actividad (str): Identifier of the evaluated learning activity.
        tipo (str): Instrument type (rubrica, lista_cotejo, escala_rango).
        titulo (str): Instrument title.
        instrumento_generado (Union[dict, InstrumentoGeneradoDetail]): Generated instrument structure.

    Returns:
        str: JSON formatted response with saved instrument ID.
    """
    try:
        db = get_db()
        act_obj_id = _ensure_object_id(id_actividad)
        inst_dict = _to_dict(instrumento_generado)

        doc = {
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "instrumento_generado": inst_dict
        }

        res = db[ASSESSMENT_INSTRUMENTS].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Assessment instrument saved successfully.",
            "id_instrumento": str(res.inserted_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving assessment instrument: {str(e)}"})


@tool("get_assessment_instrument_by_id")
def get_assessment_instrument_by_id(id_instrumento: str) -> str:
    """
    Retrieves an assessment instrument by its identifier.

    Args:
        id_instrumento (str): Unique instrument identifier.

    Returns:
        str: JSON formatted response with instrument data.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        inst = db[ASSESSMENT_INSTRUMENTS].find_one({"_id": obj_id})
        if not inst:
            return json.dumps({"status": "error", "message": f"Instrument '{id_instrumento}' not found."})
        return json.dumps({"status": "success", "instrumento": inst}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving assessment instrument: {str(e)}"})


@tool("update_assessment_instrument", args_schema=UpdateAssessmentInstrumentInput)
def update_assessment_instrument(
    id_instrumento: str,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    instrumento_generado: Optional[Union[dict, InstrumentoGeneradoDetail]] = None
) -> str:
    """
    Updates data for an existing assessment instrument.

    Args:
        id_instrumento (str): Unique identifier of the instrument to update.
        id_actividad (str, optional): Updated activity identifier.
        tipo (str, optional): Updated instrument type.
        titulo (str, optional): Updated instrument title.
        instrumento_generado (Union[dict, InstrumentoGeneradoDetail], optional): Updated instrument structure.

    Returns:
        str: JSON formatted response with update execution status.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())

        merged_updates = {}
        if id_actividad is not None:
            merged_updates["id_actividad"] = _ensure_object_id(id_actividad)
        if tipo is not None:
            merged_updates["tipo"] = str(tipo)
        if titulo is not None:
            merged_updates["titulo"] = str(titulo)
        if instrumento_generado is not None:
            merged_updates["instrumento_generado"] = _to_dict(instrumento_generado)

        updates = _clean_updates(merged_updates)

        if not updates:
            return json.dumps({"status": "error", "message": "No valid fields provided for update."})

        res = db[ASSESSMENT_INSTRUMENTS].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Instrument '{id_instrumento}' not found."})

        return json.dumps({"status": "success", "message": f"Instrument '{id_instrumento}' successfully updated."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error updating assessment instrument: {str(e)}"})


@tool("delete_assessment_instrument")
def delete_assessment_instrument(id_instrumento: str, confirm: bool = True) -> str:
    """
    Deletes an assessment instrument by its identifier.

    Args:
        id_instrumento (str): Unique identifier of the instrument to delete.
        confirm (bool, optional): Prior confirmation required for deletion. Defaults to True.

    Returns:
        str: JSON formatted response with deletion result.
    """
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMATION REQUIRED: Delete instrument '{id_instrumento}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        res = db[ASSESSMENT_INSTRUMENTS].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Instrument '{id_instrumento}' not found."})

        return json.dumps({"status": "success", "message": f"Instrument '{id_instrumento}' successfully deleted."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error deleting assessment instrument: {str(e)}"})


@tool("save_multimodal_resource", args_schema=SaveMultimodalResourceInput)
def save_multimodal_resource(
    id_actividad: str,
    tipo: str,
    titulo: str,
    url: str
) -> str:
    """
    Saves a multimodal educational resource linked to a learning activity.

    Args:
        id_actividad (str): Identifier of the learning activity.
        tipo (str): Resource type (video, imagen, documento, simulacion, lectura).
        titulo (str): Resource title.
        url (str): Resource URL link.

    Returns:
        str: JSON formatted response with saved resource ID.
    """
    try:
        db = get_db()
        act_obj_id = _ensure_object_id(id_actividad)

        doc = {
            "id_actividad": act_obj_id,
            "tipo": str(tipo),
            "titulo": str(titulo),
            "url": str(url)
        }

        res = db[MULTIMODAL_RESOURCES].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Multimodal resource saved successfully.",
            "id_recurso": str(res.inserted_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving multimodal resource: {str(e)}"})


@tool("get_multimodal_resource_by_id")
def get_multimodal_resource_by_id(id_recurso: str) -> str:
    """
    Retrieves a multimodal resource by its identifier.

    Args:
        id_recurso (str): Unique multimodal resource identifier.

    Returns:
        str: JSON formatted response with resource information.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        rec = db[MULTIMODAL_RESOURCES].find_one({"_id": obj_id})
        if not rec:
            return json.dumps({"status": "error", "message": f"Resource '{id_recurso}' not found."})
        return json.dumps({"status": "success", "recurso": rec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error reading multimodal resource: {str(e)}"})


@tool("update_multimodal_resource", args_schema=UpdateMultimodalResourceInput)
def update_multimodal_resource(
    id_recurso: str,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    url: Optional[str] = None
) -> str:
    """
    Updates information for an existing multimodal resource.

    Args:
        id_recurso (str): Unique identifier of the resource to update.
        id_actividad (str, optional): Updated activity identifier.
        tipo (str, optional): Updated resource type.
        titulo (str, optional): Updated resource title.
        url (str, optional): Updated resource URL.

    Returns:
        str: JSON formatted response with update execution status.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())

        merged_updates = {}
        if id_actividad is not None:
            merged_updates["id_actividad"] = _ensure_object_id(id_actividad)
        if tipo is not None:
            merged_updates["tipo"] = str(tipo)
        if titulo is not None:
            merged_updates["titulo"] = str(titulo)
        if url is not None:
            merged_updates["url"] = str(url)

        updates = _clean_updates(merged_updates)

        if not updates:
            return json.dumps({"status": "error", "message": "No valid fields provided for update."})

        res = db[MULTIMODAL_RESOURCES].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Resource '{id_recurso}' not found."})

        return json.dumps({"status": "success", "message": f"Resource '{id_recurso}' successfully updated."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error updating multimodal resource: {str(e)}"})


@tool("delete_multimodal_resource")
def delete_multimodal_resource(id_recurso: str, confirm: bool = True) -> str:
    """
    Deletes a multimodal resource by its identifier.

    Args:
        id_recurso (str): Unique identifier of the resource to delete.
        confirm (bool, optional): Prior confirmation required for deletion. Defaults to True.

    Returns:
        str: JSON formatted response with deletion result.
    """
    try:
        if not confirm:
            return json.dumps({"status": "pending_confirmation", "message": f"CONFIRMATION REQUIRED: Delete resource '{id_recurso}'?"}, ensure_ascii=False)

        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        res = db[MULTIMODAL_RESOURCES].delete_one({"_id": obj_id})
        if res.deleted_count == 0:
            return json.dumps({"status": "error", "message": f"Resource '{id_recurso}' not found."})

        return json.dumps({"status": "success", "message": f"Resource '{id_recurso}' successfully deleted."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error deleting multimodal resource: {str(e)}"})


@tool("get_top_frequent_courses")
def get_top_frequent_courses(config: RunnableConfig = None, id_usuario: str = "", limit: int = 4) -> str:
    """
    Obtains the most frequently used subareas or subjects in teacher lesson plans.

    Args:
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.
        limit (int, optional): Maximum count of records to retrieve. Defaults to 4.

    Returns:
        str: JSON formatted response with the list of top subareas.
    """
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Authenticated user identifier not provided or invalid."})

        user_obj_id = ObjectId(effective_id.strip())

        pipeline = [
            {"$match": {"id_usuario": user_obj_id}},
            {"$group": {"_id": "$metadatos.subarea_curricular", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]

        results = list(db[LESSON_PLANS].aggregate(pipeline))
        return json.dumps({"status": "success", "id_usuario": effective_id, "top_cursos": results}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error querying top courses: {str(e)}"})


@tool("get_paginated_lesson_plans")
def get_paginated_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", page: int = 1, limit: int = 10) -> str:
    """
    Retrieves a paginated list of teacher lesson plans belonging to the user.

    Args:
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.
        page (int, optional): Page number (starting at 1). Defaults to 1.
        limit (int, optional): Number of records per page. Defaults to 10.

    Returns:
        str: JSON formatted response with paginated lesson plans and pagination metadata.
    """
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        if not effective_id or len(effective_id.strip()) != 24:
            return json.dumps({"status": "error", "message": "Authenticated user identifier not provided or invalid."})

        user_obj_id = ObjectId(effective_id.strip())

        total_count = db[LESSON_PLANS].count_documents({"id_usuario": user_obj_id})
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
            db[LESSON_PLANS]
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
        return json.dumps({"status": "error", "message": f"Error in paginated history: {str(e)}"})


@tool("get_lesson_plan_details")
def get_lesson_plan_details(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
    """
    Retrieves full details of a teacher's lesson plan along with associated instruments and resources.

    Args:
        id_planificacion (str): Unique lesson plan identifier.
        config (RunnableConfig, optional): Execution configuration context.
        id_usuario (str, optional): User identifier.

    Returns:
        str: JSON formatted response with detailed lesson plan information.
    """
    try:
        db = get_db()
        plan_obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": plan_obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[LESSON_PLANS].find_one(query)
        if not plan:
            return json.dumps({"status": "error", "message": "Access denied or lesson plan not found for this user."})

        activity_ids = []
        for fila in plan.get("desarrollo_curricular", []):
            for act in fila.get("actividades_aprendizaje", []):
                act_id = act.get("id_actividad")
                if act_id:
                    activity_ids.append(_ensure_object_id(act_id))

        instruments = list(db[ASSESSMENT_INSTRUMENTS].find({"id_actividad": {"$in": activity_ids}})) if activity_ids else []
        resources = list(db[MULTIMODAL_RESOURCES].find({"id_actividad": {"$in": activity_ids}})) if activity_ids else []

        return json.dumps({
            "status": "success",
            "planificacion": plan,
            "instrumentos_evaluacion": instruments,
            "recursos_multimodales": resources
        }, cls=JSONEncoderCustom, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving full lesson plan details: {str(e)}"})


@tool("get_cnb_careers_list")
def get_cnb_careers_list() -> str:
    """
    Retrieves the list of available academic careers in the curriculum catalog.

    Returns:
        str: JSON formatted response with the list of career names.
    """
    try:
        db = get_db()
        raw_careers = db[AREAS].distinct("nombre_carrera")
        career_names = [str(c).strip() for c in raw_careers if c and str(c).strip()]
        return json.dumps({"status": "success", "carreras": career_names}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error obtaining careers catalog: {str(e)}"})


@tool("get_cnb_areas_by_career")
def get_cnb_areas_by_career(carrera: str, page: int = 1, limit: int = 10) -> str:
    """
    Retrieves curricular areas belonging to a specific career in the curriculum.

    Args:
        carrera (str): Career name to query.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Number of records per page. Defaults to 10.

    Returns:
        str: JSON formatted response with paginated list of curricular areas.
    """
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
        return json.dumps({"status": "error", "message": f"Error obtaining areas by career: {str(e)}"})


@tool("get_cnb_subareas_by_area_id")
def get_cnb_subareas_by_area_id(id_area: str, page: int = 1, limit: int = 10) -> str:
    """
    Retrieves curricular subareas belonging to a specific area in the curriculum.

    Args:
        id_area (str): Curricular area identifier.
        page (int, optional): Page number. Defaults to 1.
        limit (int, optional): Number of records per page. Defaults to 10.

    Returns:
        str: JSON formatted response with paginated list of curricular subareas.
    """
    try:
        db = get_db()
        area_obj_id = ObjectId(id_area.strip())
        query = {"id_area": area_obj_id}
        total_count = db[SUB_AREAS].count_documents(query)
        skip = (max(1, page) - 1) * limit

        projection = {
            "_id": 1,
            "nombre_subarea": 1
        }

        subareas_cursor = db[SUB_AREAS].find(query, projection).skip(skip).limit(limit)
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
        return json.dumps({"status": "error", "message": f"Error obtaining subareas: {str(e)}"})


def create_user_doc(data: dict) -> dict:
    """
    Creates a new user document in the system from authenticated data.

    Args:
        data (dict): Authenticated user information dictionary.

    Returns:
        dict: Operation result dictionary containing user ID.
    """
    try:
        db = get_db()
        google_id = str(data.get("google_id", "")).strip()
        email = str(data.get("email", "")).strip().lower()

        if not google_id:
            return {"status": "error", "message": "Field 'google_id' is required."}
        if not email:
            return {"status": "error", "message": "Field 'email' is required."}

        existing = db[USERS].find_one({"google_id": google_id})
        if existing:
            db[USERS].update_one({"_id": existing["_id"]}, {"$set": {"ultimo_acceso": _get_bson_timestamp()}})
            existing["_id"] = str(existing["_id"])
            return {"status": "info", "message": "Existing user.", "user": existing, "id_usuario": existing["_id"]}

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

        res = db[USERS].insert_one(user_doc)
        user_doc["_id"] = str(res.inserted_id)
        return {"status": "success", "message": "User created.", "user": user_doc, "id_usuario": user_doc["_id"]}

    except Exception as e:
        return {"status": "error", "message": f"Error creating user: {str(e)}"}


def get_user_by_google_id(google_id: str) -> Optional[dict]:
    """
    Retrieves user profile document by Google ID.

    Args:
        google_id (str): Unique Google OAuth identifier.

    Returns:
        Optional[dict]: User information or None if not found.
    """
    try:
        db = get_db()
        gid = str(google_id).strip()
        if not gid:
            return None
        user = db[USERS].find_one({"google_id": gid})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None


def get_user_profile_doc(id_usuario: str) -> Optional[dict]:
    """
    Retrieves user profile document by user ID.

    Args:
        id_usuario (str): Unique user identifier.

    Returns:
        Optional[dict]: Profile information or None if not found.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        user = db[USERS].find_one({"_id": obj_id})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None


def update_user_profile_doc(id_usuario: str, update_data: dict) -> bool:
    """
    Updates profile data of a user.

    Args:
        id_usuario (str): Unique user identifier.
        update_data (dict): Profile fields to update.

    Returns:
        bool: True if update succeeded, False otherwise.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        updates = _clean_updates(update_data)
        updates["ultimo_acceso"] = _get_bson_timestamp()

        res = db[USERS].update_one({"_id": obj_id}, {"$set": updates})
        return res.matched_count > 0
    except Exception:
        return False


def delete_user_profile_doc(id_usuario: str) -> bool:
    """
    Deletes user account from the system.

    Args:
        id_usuario (str): Unique user identifier to delete.

    Returns:
        bool: True if deleted, False otherwise.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        res = db[USERS].delete_one({"_id": obj_id})
        return res.deleted_count > 0
    except Exception:
        return False


def save_refresh_token(id_usuario: str, refresh_token: str, expires_in_days: int = 7) -> bool:
    """
    Saves or updates a session refresh token for a user.

    Args:
        id_usuario (str): Unique user identifier.
        refresh_token (str): Issued refresh token.
        expires_in_days (int, optional): Token validity in days. Defaults to 7.

    Returns:
        bool: True if stored successfully, False otherwise.
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
    Validates and retrieves an active refresh token document.

    Args:
        refresh_token (str): Refresh token to validate.

    Returns:
        Optional[dict]: Active refresh token data or None if invalid/expired.
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