import json
import hmac
import hashlib
import bson
from datetime import datetime, timezone, timedelta
from typing import Union, Dict, List, Optional
from bson import ObjectId
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


def get_mongo_client(timeout_ms: Optional[int] = None) -> MongoClient:
    mongodb_uri = get_env_variable("MONGODB_URI")
    if timeout_ms:
        return MongoClient(mongodb_uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
    return MongoClient(mongodb_uri)


def get_db():
    client = get_mongo_client()
    db_name = get_env_variable("DB_NAME")
    return client[db_name]


def check_db_connection(timeout_ms: int = 2000) -> bool:
    try:
        client = get_mongo_client(timeout_ms=timeout_ms)
        client.admin.command("ping")
        return True
    except Exception:
        return False


def extract_user_id_from_config(config: Optional[Union[RunnableConfig, dict, object]] = None) -> str:
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


def extract_teacher_name_from_config(config: Optional[Union[RunnableConfig, dict, object]] = None, user_id: str = "") -> str:
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


def _to_dict(obj: Union[dict, object]) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def _ensure_object_id(val: Union[str, ObjectId, bytes, object]) -> ObjectId:
    if isinstance(val, ObjectId):
        return val
    val_str = str(val).strip()
    if len(val_str) == 24:
        return ObjectId(val_str)
    return ObjectId()


def _clean_updates(updates: dict) -> dict:
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
        "actividades_sugeridas": _format_items(data.get("actividades_sugeridas")),
        "criterios_evaluacion_sugeridos": _format_items(data.get("criterios_evaluacion_sugeridos"))
    }
    res = db[AREAS].insert_one(doc)
    return res.inserted_id


def insert_cnb_subarea_doc(data: dict) -> ObjectId:
    db = get_db()
    doc = {
        "id_area": _ensure_object_id(data.get("id_area")),
        "nombre_subarea": str(data.get("nombre_subarea", "")).strip(),
        "competencias": data.get("competencias", [])
    }
    res = db[SUB_AREAS].insert_one(doc)
    return res.inserted_id


def insert_cnb_vector_doc(data: dict) -> ObjectId:
    db = get_db()
    doc = {
        "id_subarea": _ensure_object_id(data.get("id_subarea")),
        "nombre_subarea": str(data.get("nombre_subarea", "")).strip(),
        "tipo_nodo": str(data.get("tipo_nodo", "")).strip(),
        "referencia_jerarquica": data.get("referencia_jerarquica", []),
        "texto_a_buscar": str(data.get("texto_a_buscar", "")).strip(),
        "vector_embedding": data.get("vector_embedding", []),
        "vector_estado": bool(data.get("vector_estado", False))
    }
    res = db[VECTORS].insert_one(doc)
    return res.inserted_id


@tool("save_curricular_structure", description="Saves complete curricular area and subarea structure.", args_schema=SaveCurricularStructureInput)
def save_curricular_structure(
    nombre_carrera: str,
    nombre_area: str,
    actividades_sugeridas: List[str],
    criterios_evaluacion_sugeridos: List[str],
    subareas: List[Union[dict, Subarea]]
) -> str:
    try:
        subareas_dicts = [_to_dict(s) for s in subareas]
        area_data = {
            "nombre_carrera": nombre_carrera,
            "nombre_area": nombre_area,
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
                    "id_subarea": sub_id,
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
                        "id_subarea": sub_id,
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
                            "id_subarea": sub_id,
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
        return json.dumps(response, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving curricular structure: {str(e)}"})


@tool("save_lesson_plan", description="Saves a generated lesson plan into the database.", args_schema=SaveLessonPlanInput)
def save_lesson_plan(
    metadatos: Union[dict, MetadatosPlanInput],
    encabezado: Union[dict, EncabezadoPlan],
    desarrollo_curricular: List[Union[dict, FilaCurricularPlan]],
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    try:
        db = get_db()
        effective_id = extract_user_id_from_config(config) or id_usuario
        user_obj_id = _ensure_object_id(effective_id) if effective_id else ObjectId()

        meta_dict = _to_dict(metadatos)
        enc_dict = _to_dict(encabezado)

        metadatos_doc = {
            "carrera": str(meta_dict.get("carrera", "")),
            "subarea_curricular": str(meta_dict.get("subarea_curricular", "")),
            "fecha_creacion": datetime.now(timezone.utc),
            "estado": str(meta_dict.get("estado", "finalizado"))
        }

        formatted_desarrollo = []
        for item in desarrollo_curricular:
            item_dict = _to_dict(item)
            acts = item_dict.get("actividades_aprendizaje", [])
            formatted_acts = []
            for act in acts:
                act_dict = _to_dict(act)
                act_id_val = act_dict.get("id_actividad")
                act_dict["id_actividad"] = _ensure_object_id(act_id_val) if act_id_val else ObjectId()
                formatted_acts.append(act_dict)

            item_dict["actividades_aprendizaje"] = formatted_acts
            formatted_desarrollo.append(item_dict)

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
                "duracion": str(enc_dict.get("duracion", "")),
                "cantidad_periodos": int(enc_dict.get("cantidad_periodos", 0)),
                "duracion_periodos": int(enc_dict.get("duracion_periodos", 0))
            },
            "desarrollo_curricular": formatted_desarrollo
        }

        res = db[LESSON_PLANS].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Teacher lesson plan created successfully.",
            "id_planificacion": str(res.inserted_id),
            "id_usuario": str(user_obj_id)
        }, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error creating lesson plan: {str(e)}"})


@tool("get_planification_by_id", description="Retrieves a lesson plan by its unique ID.")
def get_planification_by_id(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
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

        return json.dumps({"status": "success", "planificacion": plan}, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving lesson plan: {str(e)}"})


@tool("get_learning_activity_by_id", description="Retrieves a learning activity by activity ID.")
def get_learning_activity_by_id(id_actividad: str) -> str:
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

        return json.dumps({"status": "success", "actividad": results[0]}, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving learning activity: {str(e)}"})


@tool("update_lesson_plan", description="Updates an existing lesson plan.", args_schema=UpdateLessonPlanInput)
def update_lesson_plan(
    id_planificacion: str,
    metadatos: Optional[Union[dict, MetadatosPlanInput]] = None,
    encabezado: Optional[Union[dict, EncabezadoPlan]] = None,
    desarrollo_curricular: Optional[List[Union[dict, FilaCurricularPlan]]] = None,
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
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


@tool("delete_lesson_plan", description="Deletes a lesson plan by ID.")
def delete_lesson_plan(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "", confirm: bool = True) -> str:
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
        for item in plan.get("desarrollo_curricular", []):
            for act in item.get("actividades_aprendizaje", []):
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


@tool("get_cnb_area_by_id", description="Retrieves a CNB area document by ID.")
def get_cnb_area_by_id(id_area: str) -> str:
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        area = db[AREAS].find_one({"_id": obj_id})
        if not area:
            return json.dumps({"status": "error", "message": f"Curricular area '{id_area}' not found."})
        return json.dumps({"status": "success", "area": area}, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving curricular area: {str(e)}"})


@tool("get_cnb_subarea_by_id", description="Retrieves a CNB subarea document by ID.")
def get_cnb_subarea_by_id(id_subarea: str) -> str:
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        subarea = db[SUB_AREAS].find_one({"_id": obj_id})
        if not subarea:
            return json.dumps({"status": "error", "message": f"Curricular subarea '{id_subarea}' not found."})
        return json.dumps({"status": "success", "subarea": subarea}, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving curricular subarea: {str(e)}"})


@tool("get_cnb_vector_by_id", description="Retrieves a CNB vector document by ID.")
def get_cnb_vector_by_id(id_vector: str) -> str:
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        vec = db[VECTORS].find_one({"_id": obj_id})
        if not vec:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' not found."})
        return json.dumps({"status": "success", "vector": vec}, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving vector record: {str(e)}"})


def update_cnb_vector(id_vector: str, update_data: Dict[str, Union[str, int, float, bool, List[float], List[str]]]) -> str:
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


@tool("save_assessment_instrument", description="Saves an evaluation assessment instrument.", args_schema=SaveAssessmentInstrumentInput)
def save_assessment_instrument(
    id_actividad: str,
    tipo: str,
    titulo: str,
    instrumento_generado: Union[dict, InstrumentoGeneradoDetail]
) -> str:
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
        }, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving assessment instrument: {str(e)}"})


@tool("get_assessment_instrument_by_id", description="Retrieves an assessment instrument by ID.")
def get_assessment_instrument_by_id(id_instrumento: str) -> str:
    try:
        db = get_db()
        obj_id = ObjectId(id_instrumento.strip())
        inst = db[ASSESSMENT_INSTRUMENTS].find_one({"_id": obj_id})
        if not inst:
            return json.dumps({"status": "error", "message": f"Instrument '{id_instrumento}' not found."})
        return json.dumps({"status": "success", "instrumento": inst}, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving assessment instrument: {str(e)}"})


@tool("update_assessment_instrument", description="Updates an evaluation instrument.", args_schema=UpdateAssessmentInstrumentInput)
def update_assessment_instrument(
    id_instrumento: str,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    instrumento_generado: Optional[Union[dict, InstrumentoGeneradoDetail]] = None
) -> str:
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


@tool("delete_assessment_instrument", description="Deletes an assessment instrument by ID.")
def delete_assessment_instrument(id_instrumento: str, confirm: bool = True) -> str:
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


@tool("save_multimodal_resource", description="Saves a multimodal educational resource.", args_schema=SaveMultimodalResourceInput)
def save_multimodal_resource(
    id_actividad: str,
    tipo: str,
    titulo: str,
    url: str
) -> str:
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
        }, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error saving multimodal resource: {str(e)}"})


@tool("get_multimodal_resource_by_id", description="Retrieves a multimodal resource by ID.")
def get_multimodal_resource_by_id(id_recurso: str) -> str:
    try:
        db = get_db()
        obj_id = ObjectId(id_recurso.strip())
        rec = db[MULTIMODAL_RESOURCES].find_one({"_id": obj_id})
        if not rec:
            return json.dumps({"status": "error", "message": f"Resource '{id_recurso}' not found."})
        return json.dumps({"status": "success", "recurso": rec}, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error reading multimodal resource: {str(e)}"})


@tool("update_multimodal_resource", description="Updates a multimodal resource.", args_schema=UpdateMultimodalResourceInput)
def update_multimodal_resource(
    id_recurso: str,
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    url: Optional[str] = None
) -> str:
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


@tool("delete_multimodal_resource", description="Deletes a multimodal resource by ID.")
def delete_multimodal_resource(id_recurso: str, confirm: bool = True) -> str:
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


@tool("get_top_frequent_courses", description="Retrieves top most frequent courses for the user.")
def get_top_frequent_courses(config: RunnableConfig = None, id_usuario: str = "", limit: int = 4) -> str:
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
        return json.dumps({"status": "success", "id_usuario": effective_id, "top_cursos": results}, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error querying top courses: {str(e)}"})


@tool("get_paginated_lesson_plans", description="Retrieves paginated lesson plans for the user.")
def get_paginated_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", page: int = 1, limit: int = 10) -> str:
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
        }, default=str, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error in paginated history: {str(e)}"})


@tool("get_lesson_plan_details", description="Retrieves full details of a lesson plan by ID.")
def get_lesson_plan_details(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "") -> str:
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
        for item in plan.get("desarrollo_curricular", []):
            for act in item.get("actividades_aprendizaje", []):
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
        }, default=str, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error retrieving full lesson plan details: {str(e)}"})


@tool("get_cnb_careers_list", description="Retrieves list of available CNB careers catalog.")
def get_cnb_careers_list() -> str:
    try:
        db = get_db()
        raw_careers = db[AREAS].distinct("nombre_carrera")
        career_names = [str(c).strip() for c in raw_careers if c and str(c).strip()]
        return json.dumps({"status": "success", "carreras": career_names}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error obtaining careers catalog: {str(e)}"})


@tool("get_cnb_areas_by_career", description="Retrieves CNB areas for a given career.")
def get_cnb_areas_by_career(carrera: str, page: int = 1, limit: int = 10) -> str:
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


@tool("get_cnb_subareas_by_area_id", description="Retrieves CNB subareas by area ID.")
def get_cnb_subareas_by_area_id(id_area: str, page: int = 1, limit: int = 10) -> str:
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
            db[USERS].update_one({"_id": existing["_id"]}, {"$set": {"ultimo_acceso": datetime.now(timezone.utc)}})
            existing["_id"] = str(existing["_id"])
            return {"status": "info", "message": "Existing user.", "user": existing, "id_usuario": existing["_id"]}

        now_dt = datetime.now(timezone.utc)
        user_doc = {
            "google_id": google_id,
            "nombres": str(data.get("nombres", "")),
            "apellidos": str(data.get("apellidos", "")),
            "email": email,
            "estado": str(data.get("estado", "activo")),
            "fecha_creacion": now_dt,
            "ultimo_acceso": now_dt,
            "foto_perfil": str(data.get("foto_perfil", "")),
            "rol": str(data.get("rol", "docente"))
        }

        res = db[USERS].insert_one(user_doc)
        user_doc["_id"] = str(res.inserted_id)
        return {"status": "success", "message": "User created.", "user": user_doc, "id_usuario": user_doc["_id"]}

    except Exception as e:
        return {"status": "error", "message": f"Error creating user: {str(e)}"}


def get_user_by_google_id(google_id: str) -> Optional[dict]:
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
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        updates = _clean_updates(update_data)
        updates["ultimo_acceso"] = datetime.now(timezone.utc)

        res = db[USERS].update_one({"_id": obj_id}, {"$set": updates})
        return res.matched_count > 0
    except Exception:
        return False


def delete_user_profile_doc(id_usuario: str) -> bool:
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        res = db[USERS].delete_one({"_id": obj_id})
        return res.deleted_count > 0
    except Exception:
        return False


def hash_session_id(session_id_hex: str) -> bson.Binary:
    secret = get_env_variable("SESSION_SECRET").encode("utf-8")
    digest = hmac.new(secret, str(session_id_hex).strip().encode("utf-8"), hashlib.sha256).digest()
    return bson.Binary(digest)


def hash_refresh_token(refresh_token_hex: str) -> bson.Binary:
    secret = get_env_variable("REFRESH_SECRET").encode("utf-8")
    digest = hmac.new(secret, str(refresh_token_hex).strip().encode("utf-8"), hashlib.sha256).digest()
    return bson.Binary(digest)


def save_session_doc(
    id_usuario: str,
    session_id: str,
    access_token: str,
    refresh_token: str,
    expires_in_days: int = 7
) -> bool:
    try:
        db = get_db()
        user_obj_id = _ensure_object_id(id_usuario)
        now_dt = datetime.now(timezone.utc)
        session_bin = hash_session_id(session_id)
        refresh_bin = hash_refresh_token(refresh_token)

        doc = {
            "id_usuario": user_obj_id,
            "session_id": session_bin,
            "access_token": str(access_token).strip(),
            "refresh_token": refresh_bin,
            "fecha_creacion": now_dt,
            "fecha_expiracion": now_dt + timedelta(days=expires_in_days)
        }
        db[REFRESH_TOKENS].update_one(
            {"session_id": session_bin},
            {"$set": doc},
            upsert=True
        )
        return True
    except Exception:
        return False


def get_session_by_session_id(session_id: str) -> Optional[dict]:
    try:
        db = get_db()
        sid_str = str(session_id).strip()
        if not sid_str:
            return None
        session_bin = hash_session_id(sid_str)
        doc = db[REFRESH_TOKENS].find_one({"session_id": session_bin})
        if not doc:
            return None
        now = datetime.now(timezone.utc)
        exp = doc.get("fecha_expiracion")
        if not exp or not isinstance(exp, datetime):
            return None
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            db[REFRESH_TOKENS].delete_one({"_id": doc["_id"]})
            return None
        doc["_id"] = str(doc["_id"])
        if "id_usuario" in doc:
            doc["id_usuario"] = str(doc["id_usuario"])
        return doc
    except Exception:
        return None


def update_session_tokens(
    session_id: str,
    new_access_token: str,
    new_refresh_token: str
) -> bool:
    try:
        db = get_db()
        sid_str = str(session_id).strip()
        if not sid_str:
            return False
        session_bin = hash_session_id(sid_str)
        new_refresh_bin = hash_refresh_token(new_refresh_token)

        res = db[REFRESH_TOKENS].update_one(
            {"session_id": session_bin},
            {
                "$set": {
                    "access_token": str(new_access_token).strip(),
                    "refresh_token": new_refresh_bin
                }
            }
        )
        return res.modified_count > 0 or res.matched_count > 0
    except Exception:
        return False


def delete_session_by_session_id(session_id: str) -> bool:
    try:
        db = get_db()
        sid_str = str(session_id).strip()
        if not sid_str:
            return False
        session_bin = hash_session_id(sid_str)
        res = db[REFRESH_TOKENS].delete_one({"session_id": session_bin})
        return res.deleted_count > 0
    except Exception:
        return False