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
    """
    Genera un objeto BSON Timestamp de MongoDB.

    Returns:
        Timestamp: Marca de tiempo BSON actual.
    """
    return Timestamp(int(time.time()), 1)


def get_mongo_client(timeout_ms: Optional[int] = None) -> MongoClient:
    """
    Crea una instancia de MongoClient utilizando la URI de conexión configurada.

    Args:
        timeout_ms (int, opcional): Tiempo de espera máximo en milisegundos.

    Returns:
        MongoClient: Cliente de MongoDB configurado.
    """
    mongodb_uri = get_env_variable("MONGODB_URI")
    if timeout_ms:
        return MongoClient(mongodb_uri, serverSelectionTimeoutMS=timeout_ms, connectTimeoutMS=timeout_ms)
    return MongoClient(mongodb_uri)


def get_db():
    """
    Obtiene la instancia de la base de datos MongoDB.

    Returns:
        Database: Instancia de la base de datos de la aplicación.
    """
    client = get_mongo_client()
    db_name = get_env_variable("DB_NAME")
    return client[db_name]


def check_db_connection(timeout_ms: int = 2000) -> bool:
    """
    Verifica la conectividad activa con la base de datos MongoDB.

    Args:
        timeout_ms (int, opcional): Tiempo límite de espera en milisegundos. Por defecto 2000.

    Returns:
        bool: True si la base de datos responde correctamente, False en caso contrario.
    """
    try:
        client = get_mongo_client(timeout_ms=timeout_ms)
        client.admin.command("ping")
        return True
    except Exception:
        return False


def extract_user_id_from_config(config: Optional[Any] = None) -> str:
    """
    Extrae el identificador del usuario desde la configuración de ejecución de LangGraph.

    Args:
        config (opcional): Objeto RunnableConfig o diccionario de configuración.

    Returns:
        str: Identificador único de usuario extraído o cadena vacía.
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
    Obtiene el nombre completo del docente autenticado a partir de la configuración o del identificador de usuario.

    Args:
        config (opcional): Objeto RunnableConfig o diccionario de configuración.
        user_id (str, opcional): Identificador del usuario.

    Returns:
        str: Nombre del docente o 'Docente' por defecto.
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
            user_doc = db[USUARIOS].find_one({"_id": ObjectId(effective_id.strip())})
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
    Codificador personalizado de JSON para objetos ObjectId, Timestamp y datetime de MongoDB.
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
    Convierte un objeto Pydantic o diccionario genérico en un diccionario de Python.

    Args:
        obj (Any): Instancia de Pydantic BaseModel o diccionario.

    Returns:
        dict: Diccionario de Python resultante.
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
    Convierte un valor de entrada en un objeto ObjectId de MongoDB.

    Args:
        val (Any): Cadena de 24 caracteres hexadecimales u ObjectId existente.

    Returns:
        ObjectId: Instancia de ObjectId.
    """
    if isinstance(val, ObjectId):
        return val
    val_str = str(val).strip()
    if len(val_str) == 24:
        return ObjectId(val_str)
    return ObjectId()


def _clean_updates(updates: dict) -> dict:
    """
    Limpia un diccionario de actualización omitiendo campos no editables e identificadores nulos.

    Args:
        updates (dict): Diccionario de campos a actualizar.

    Returns:
        dict: Diccionario procesado y saneado.
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
    Inserta un nuevo registro de área curricular.

    Args:
        data (dict): Información del área curricular.

    Returns:
        ObjectId: Identificador del documento insertado.
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
    Inserta una subárea curricular en la base de datos.

    Args:
        data (dict): Información de la subárea curricular.

    Returns:
        ObjectId: Identificador del documento insertado.
    """
    db = get_db()
    doc = {
        "id_area": _ensure_object_id(data.get("id_area")),
        "nombre_subarea": str(data.get("nombre_subarea", "")).strip(),
        "competencias": data.get("competencias", []),
        "fecha_creacion": _get_bson_timestamp()
    }
    res = db[SUBAREAS].insert_one(doc)
    return res.inserted_id


def insert_cnb_vector_doc(data: dict) -> ObjectId:
    """
    Inserta un nodo para indexación vectorial.

    Args:
        data (dict): Información del nodo a indexar.

    Returns:
        ObjectId: Identificador del documento insertado.
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
    res = db[VECTORES].insert_one(doc)
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
    Guarda la estructura curricular del CNB con sus áreas y subáreas.

    Args:
        nombre_carrera (str): Nombre oficial de la carrera.
        nombre_area (str): Nombre del área curricular.
        competencias_area (List[str]): Competencias del área.
        actividades_sugeridas (List[str]): Actividades sugeridas del área.
        criterios_evaluacion_sugeridos (List[str]): Criterios de evaluación sugeridos.
        subareas (List[Union[dict, Subarea]]): Subáreas pertenecientes al área.

    Returns:
        str: Respuesta en formato JSON con el estado de la operación y el ID creado.
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


@tool("save_lesson_plan", args_schema=SaveLessonPlanInput)
def save_lesson_plan(
    metadatos: Union[dict, MetadatosPlanInput],
    encabezado: Union[dict, EncabezadoPlan],
    desarrollo_curricular: List[Union[dict, FilaCurricularPlan]],
    config: RunnableConfig = None,
    id_usuario: str = ""
) -> str:
    """
    Guarda una planificación docente en la base de datos.

    Args:
        metadatos (Union[dict, MetadatosPlanInput]): Datos de metadatos de la planificación.
        encabezado (Union[dict, EncabezadoPlan]): Datos generales del encabezado.
        desarrollo_curricular (List[Union[dict, FilaCurricularPlan]]): Filas de desarrollo curricular.
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.

    Returns:
        str: Respuesta en formato JSON con el ID de la planificación guardada.
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
    """
    Recupera una planificación docente por su identificador.

    Args:
        id_planificacion (str): Identificador único de la planificación.
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.

    Returns:
        str: Respuesta en formato JSON con los detalles de la planificación encontrada.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_planificacion.strip())

        effective_id = extract_user_id_from_config(config) or id_usuario
        query = {"_id": obj_id}
        if effective_id and len(effective_id.strip()) == 24:
            query["id_usuario"] = ObjectId(effective_id.strip())

        plan = db[PLANIFICACION].find_one(query)
        if not plan:
            return json.dumps({"status": "error", "message": f"Acceso denegado o planificación '{id_planificacion}' no encontrada."})

        return json.dumps({"status": "success", "planificacion": plan}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar planificación: {str(e)}"})


@tool("get_learning_activity_by_id")
def get_learning_activity_by_id(id_actividad: str) -> str:
    """
    Recupera una actividad de aprendizaje específica por su identificador utilizando desestructuración en pipeline.

    Args:
        id_actividad (str): Identificador único de la actividad de aprendizaje.

    Returns:
        str: Respuesta en formato JSON con los datos desestructurados de la actividad de aprendizaje encontrada.
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

        results = list(db[PLANIFICACION].aggregate(pipeline))
        if not results:
            return json.dumps({"status": "error", "message": f"Actividad de aprendizaje '{id_actividad}' no encontrada."})

        return json.dumps({"status": "success", "actividad": results[0]}, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar actividad de aprendizaje: {str(e)}"})


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
    Actualiza los campos especificados de una planificación docente existente.

    Args:
        id_planificacion (str): Identificador único de la planificación a actualizar.
        metadatos (Union[dict, MetadatosPlanInput], opcional): Datos de metadatos actualizados.
        encabezado (Union[dict, EncabezadoPlan], opcional): Datos del encabezado actualizados.
        desarrollo_curricular (List[Union[dict, FilaCurricularPlan]], opcional): Desarrollo curricular actualizado.
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.

    Returns:
        str: Respuesta en formato JSON con el resultado de la actualización.
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
            "message": f"Planificación '{id_planificacion}' actualizada exitosamente.",
            "modified_count": res.modified_count
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar la planificación: {str(e)}"})


@tool("delete_lesson_plan")
def delete_lesson_plan(id_planificacion: str, config: RunnableConfig = None, id_usuario: str = "", confirm: bool = True) -> str:
    """
    Elimina una planificación docente por su identificador.

    Args:
        id_planificacion (str): Identificador único de la planificación a eliminar.
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.
        confirm (bool, opcional): Confirmación previa para la eliminación. Por defecto True.

    Returns:
        str: Respuesta en formato JSON con el estado de la eliminación.
    """
    try:
        if not confirm:
            return json.dumps({
                "status": "pending_confirmation",
                "message": f"CONFIRMACIÓN REQUERIDA: ¿Está seguro de eliminar la planificación '{id_planificacion}'?"
            }, ensure_ascii=False)

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
                "message": f"Acceso denegado o planificación '{id_planificacion}' no encontrada para eliminar."
            }, ensure_ascii=False)

        activity_ids = []
        for fila in plan.get("desarrollo_curricular", []):
            for act in fila.get("actividades_aprendizaje", []):
                act_id = act.get("id_actividad")
                if act_id:
                    activity_ids.append(_ensure_object_id(act_id))

        res = db[PLANIFICACION].delete_one({"_id": obj_id})

        if activity_ids:
            db[EVALUACION].delete_many({"id_actividad": {"$in": activity_ids}})
            db[RECURSOS].delete_many({"id_actividad": {"$in": activity_ids}})

        return json.dumps({
            "status": "success",
            "message": f"Planificación '{id_planificacion}' e instrumentos/recursos asociados eliminados exitosamente."
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al eliminar la planificación: {str(e)}"})


@tool("get_cnb_area_by_id")
def get_cnb_area_by_id(id_area: str) -> str:
    """
    Obtiene los datos de un área curricular por su identificador.

    Args:
        id_area (str): Identificador del área curricular.

    Returns:
        str: Respuesta en formato JSON con la información del área curricular.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_area.strip())
        area = db[AREAS].find_one({"_id": obj_id})
        if not area:
            return json.dumps({"status": "error", "message": f"Área curricular '{id_area}' no encontrada."})
        return json.dumps({"status": "success", "area": area}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar área curricular: {str(e)}"})


@tool("get_cnb_subarea_by_id")
def get_cnb_subarea_by_id(id_subarea: str) -> str:
    """
    Obtiene los datos de una subárea curricular por su identificador.

    Args:
        id_subarea (str): Identificador de la subárea curricular.

    Returns:
        str: Respuesta en formato JSON con la información de la subárea curricular.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_subarea.strip())
        subarea = db[SUBAREAS].find_one({"_id": obj_id})
        if not subarea:
            return json.dumps({"status": "error", "message": f"Subárea curricular '{id_subarea}' no encontrada."})
        return json.dumps({"status": "success", "subarea": subarea}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar subárea curricular: {str(e)}"})


@tool("get_cnb_vector_by_id")
def get_cnb_vector_by_id(id_vector: str) -> str:
    """
    Obtiene un nodo de indexación vectorial por su identificador.

    Args:
        id_vector (str): Identificador del nodo vectorial.

    Returns:
        str: Respuesta en formato JSON con la información del nodo vectorial.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        vec = db[VECTORES].find_one({"_id": obj_id})
        if not vec:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})
        return json.dumps({"status": "success", "vector": vec}, cls=JSONEncoderCustom, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al buscar registro vectorial: {str(e)}"})


def update_cnb_vector(id_vector: str, update_data: Dict[str, Any]) -> str:
    """
    Actualiza la información de un nodo vectorial existente.

    Args:
        id_vector (str): Identificador del nodo vectorial a actualizar.
        update_data (Dict[str, Any]): Datos de actualización.

    Returns:
        str: Respuesta en formato JSON con el estado de la actualización.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_vector.strip())
        updates = _clean_updates(update_data)

        res = db[VECTORES].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Vector '{id_vector}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Vector '{id_vector}' actualizado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar registro vectorial: {str(e)}"})


def delete_cnb_vector(id_vector: str, confirm: bool = True) -> str:
    """
    Elimina un nodo vectorial por su identificador.

    Args:
        id_vector (str): Identificador del nodo a eliminar.
        confirm (bool, opcional): Confirmación previa para la eliminación. Por defecto True.

    Returns:
        str: Respuesta en formato JSON con el resultado de la eliminación.
    """
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
        return json.dumps({"status": "error", "message": f"Error al eliminar registro vectorial: {str(e)}"})


@tool("save_assessment_instrument", args_schema=SaveAssessmentInstrumentInput)
def save_assessment_instrument(
    id_actividad: str,
    tipo: str,
    titulo: str,
    instrumento_generado: Union[dict, InstrumentoGeneradoDetail]
) -> str:
    """
    Guarda un instrumento de evaluación vinculado a una actividad de aprendizaje.

    Args:
        id_actividad (str): Identificador de la actividad evaluada.
        tipo (str): Tipo de instrumento (rubrica, lista_cotejo, escala_rango).
        titulo (str): Título del instrumento.
        instrumento_generado (Union[dict, InstrumentoGeneradoDetail]): Estructura del instrumento generado.

    Returns:
        str: Respuesta en formato JSON con el ID del instrumento guardado.
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

        res = db[EVALUACION].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Instrumento de evaluación guardado exitosamente.",
            "id_instrumento": str(res.inserted_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el instrumento de evaluación: {str(e)}"})


@tool("get_assessment_instrument_by_id")
def get_assessment_instrument_by_id(id_instrumento: str) -> str:
    """
    Recupera un instrumento de evaluación por su identificador.

    Args:
        id_instrumento (str): Identificador único del instrumento.

    Returns:
        str: Respuesta en formato JSON con los datos del instrumento.
    """
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
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    instrumento_generado: Optional[Union[dict, InstrumentoGeneradoDetail]] = None
) -> str:
    """
    Actualiza los datos de un instrumento de evaluación existente.

    Args:
        id_instrumento (str): Identificador único del instrumento a actualizar.
        id_actividad (str, opcional): Identificador de actividad actualizado.
        tipo (str, opcional): Tipo de instrumento actualizado.
        titulo (str, opcional): Título del instrumento actualizado.
        instrumento_generado (Union[dict, InstrumentoGeneradoDetail], opcional): Estructura del instrumento actualizada.

    Returns:
        str: Respuesta en formato JSON con el resultado de la actualización.
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
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        res = db[EVALUACION].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Instrumento '{id_instrumento}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Instrumento '{id_instrumento}' actualizado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar instrumento de evaluación: {str(e)}"})


@tool("delete_assessment_instrument")
def delete_assessment_instrument(id_instrumento: str, confirm: bool = True) -> str:
    """
    Elimina un instrumento de evaluación por su identificador.

    Args:
        id_instrumento (str): Identificador único del instrumento a eliminar.
        confirm (bool, opcional): Confirmación previa para la eliminación. Por defecto True.

    Returns:
        str: Respuesta en formato JSON con el resultado de la eliminación.
    """
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


@tool("save_multimodal_resource", args_schema=SaveMultimodalResourceInput)
def save_multimodal_resource(
    id_actividad: str,
    tipo: str,
    titulo: str,
    url: str
) -> str:
    """
    Guarda un recurso didáctico multimodal vinculado a una actividad de aprendizaje.

    Args:
        id_actividad (str): Identificador de la actividad de aprendizaje.
        tipo (str): Tipo de recurso (video, imagen, documento, simulacion, lectura).
        titulo (str): Título del recurso didáctico.
        url (str): Enlace URL del recurso.

    Returns:
        str: Respuesta en formato JSON con el ID del recurso guardado.
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

        res = db[RECURSOS].insert_one(doc)
        return json.dumps({
            "status": "success",
            "message": "Recurso multimodal guardado exitosamente.",
            "id_recurso": str(res.inserted_id)
        }, cls=JSONEncoderCustom, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al guardar el recurso multimodal: {str(e)}"})


@tool("get_multimodal_resource_by_id")
def get_multimodal_resource_by_id(id_recurso: str) -> str:
    """
    Recupera un recurso multimodal por su identificador.

    Args:
        id_recurso (str): Identificador único del recurso multimodal.

    Returns:
        str: Respuesta en formato JSON con la información del recurso.
    """
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
    id_actividad: Optional[str] = None,
    tipo: Optional[str] = None,
    titulo: Optional[str] = None,
    url: Optional[str] = None
) -> str:
    """
    Actualiza la información de un recurso multimodal existente.

    Args:
        id_recurso (str): Identificador único del recurso a actualizar.
        id_actividad (str, opcional): Identificador de la actividad actualizado.
        tipo (str, opcional): Tipo de recurso actualizado.
        titulo (str, opcional): Título del recurso actualizado.
        url (str, opcional): URL del recurso actualizada.

    Returns:
        str: Respuesta en formato JSON con el resultado de la actualización.
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
            return json.dumps({"status": "error", "message": "No se proporcionaron campos válidos para actualizar."})

        res = db[RECURSOS].update_one({"_id": obj_id}, {"$set": updates})
        if res.matched_count == 0:
            return json.dumps({"status": "error", "message": f"Recurso '{id_recurso}' no encontrado."})

        return json.dumps({"status": "success", "message": f"Recurso '{id_recurso}' actualizado exitosamente."}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al actualizar recurso multimodal: {str(e)}"})


@tool("delete_multimodal_resource")
def delete_multimodal_resource(id_recurso: str, confirm: bool = True) -> str:
    """
    Elimina un recurso multimodal por su identificador.

    Args:
        id_recurso (str): Identificador único del recurso a eliminar.
        confirm (bool, opcional): Confirmación previa para la eliminación. Por defecto True.

    Returns:
        str: Respuesta en formato JSON con el resultado de la eliminación.
    """
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


@tool("get_top_frequent_courses")
def get_top_frequent_courses(config: RunnableConfig = None, id_usuario: str = "", limit: int = 4) -> str:
    """
    Obtiene las subáreas o asignaturas más frecuentemente utilizadas en planificaciones del docente.

    Args:
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.
        limit (int, opcional): Cantidad máxima de registros a obtener. Por defecto 4.

    Returns:
        str: Respuesta en formato JSON con el listado de subáreas más frecuentes.
    """
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



@tool("get_paginated_lesson_plans")
def get_paginated_lesson_plans(config: RunnableConfig = None, id_usuario: str = "", page: int = 1, limit: int = 10) -> str:
    """
    Obtiene una lista paginada de planificaciones docentes pertenecientes al usuario.

    Args:
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.
        page (int, opcional): Número de página (iniciando en 1). Por defecto 1.
        limit (int, opcional): Cantidad de registros por página. Por defecto 10.

    Returns:
        str: Respuesta en formato JSON con la lista de planificaciones paginadas y metadatos.
    """
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
    """
    Obtiene los detalles completos de una planificación docente junto a sus instrumentos y recursos asociados.

    Args:
        id_planificacion (str): Identificador único de la planificación.
        config (RunnableConfig, opcional): Configuración de ejecución del flujo.
        id_usuario (str, opcional): Identificador del usuario.

    Returns:
        str: Respuesta en formato JSON con la información detallada de la planificación.
    """
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

        activity_ids = []
        for fila in plan.get("desarrollo_curricular", []):
            for act in fila.get("actividades_aprendizaje", []):
                act_id = act.get("id_actividad")
                if act_id:
                    activity_ids.append(_ensure_object_id(act_id))

        instruments = list(db[EVALUACION].find({"id_actividad": {"$in": activity_ids}})) if activity_ids else []
        resources = list(db[RECURSOS].find({"id_actividad": {"$in": activity_ids}})) if activity_ids else []

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
    """
    Obtiene la lista de carreras académicas disponibles en el currículum.

    Returns:
        str: Respuesta en formato JSON con la lista de nombres de carreras.
    """
    try:
        db = get_db()
        raw_careers = db[AREAS].distinct("nombre_carrera")
        career_names = [str(c).strip() for c in raw_careers if c and str(c).strip()]
        return json.dumps({"status": "success", "carreras": career_names}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Error al obtener catálogo de carreras: {str(e)}"})


@tool("get_cnb_areas_by_career")
def get_cnb_areas_by_career(carrera: str, page: int = 1, limit: int = 10) -> str:
    """
    Obtiene las áreas curriculares pertenecientes a una carrera específica del currículum.

    Args:
        carrera (str): Nombre de la carrera a consultar.
        page (int, opcional): Número de página. Por defecto 1.
        limit (int, opcional): Cantidad de registros por página. Por defecto 10.

    Returns:
        str: Respuesta en formato JSON con la lista paginada de áreas curriculares.
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
        return json.dumps({"status": "error", "message": f"Error al obtener áreas por carrera: {str(e)}"})


@tool("get_cnb_subareas_by_area_id")
def get_cnb_subareas_by_area_id(id_area: str, page: int = 1, limit: int = 10) -> str:
    """
    Obtiene las subáreas curriculares pertenecientes a un área específica del currículum.

    Args:
        id_area (str): Identificador del área curricular.
        page (int, opcional): Número de página. Por defecto 1.
        limit (int, opcional): Cantidad de registros por página. Por defecto 10.

    Returns:
        str: Respuesta en formato JSON con la lista paginada de subáreas curriculares.
    """
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


def create_user_doc(data: dict) -> dict:
    """
    Crea un nuevo usuario en el sistema a partir de datos autenticados.

    Args:
        data (dict): Información del usuario autenticado.

    Returns:
        dict: Diccionario con el resultado de la operación e ID de usuario.
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
    Obtiene la información de un usuario por su identificador de Google.

    Args:
        google_id (str): Identificador único de Google OAuth.

    Returns:
        Optional[dict]: Información del usuario o None si no existe.
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
    """
    Obtiene el perfil de un usuario por su identificador único.

    Args:
        id_usuario (str): Identificador único de usuario.

    Returns:
        Optional[dict]: Información del perfil o None si no se encuentra.
    """
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
    """
    Actualiza los datos del perfil de un usuario.

    Args:
        id_usuario (str): Identificador único del usuario.
        update_data (dict): Campos del perfil a actualizar.

    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario.
    """
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
    """
    Elimina la cuenta de usuario del sistema.

    Args:
        id_usuario (str): Identificador único del usuario a eliminar.

    Returns:
        bool: True si la cuenta fue eliminada, False en caso contrario.
    """
    try:
        db = get_db()
        obj_id = ObjectId(id_usuario.strip())
        res = db[USUARIOS].delete_one({"_id": obj_id})
        return res.deleted_count > 0
    except Exception:
        return False


def save_refresh_token(id_usuario: str, refresh_token: str, expires_in_days: int = 7) -> bool:
    """
    Guarda o actualiza un token de refresco para la sesión de un usuario.

    Args:
        id_usuario (str): Identificador único del usuario.
        refresh_token (str): Token de refresco emitido.
        expires_in_days (int, opcional): Días de validez del token. Por defecto 7.

    Returns:
        bool: True si el token fue almacenado exitosamente, False en caso contrario.
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
    Valida y recupera un token de refresco activo.

    Args:
        refresh_token (str): Token de refresco a validar.

    Returns:
        Optional[dict]: Datos del token de refresco activo o None si es inválido/expirado.
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