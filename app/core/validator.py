import re
import json
from typing import Dict, Any, Union, Optional


def validate_subagent_response(subagent_name: str, raw_output: Union[str, dict, Exception]) -> str:
    """
    Validador Determinista de Respuestas de Subagentes según el estándar de LangChain/DeepAgents.
    Retorna la respuesta del artefacto completa sin truncar ni limitar su longitud.
    
    Estrategia de Validación:
    1. Tipos de Excepción (isinstance):
       - PermissionError, KeyError, ValueError -> estado: "blocked" (Falta de datos o permisos).
       - Excepción genérica u otro error de ejecución -> estado: "failed".
    2. Diccionarios/JSON Estructurados:
       - status == "error" con código de bloqueo (MISSING_INPUT, PERMISSION_DENIED) -> estado: "blocked".
       - status == "error" con fallo de ejecución -> estado: "failed".
    3. Ejecución Exitosa:
       - Extrae IDs de artefactos (24 caracteres hex) o retorna el contenido completo -> estado: "success".
    """
    # 1. Manejo determinista por Tipo de Excepción
    if isinstance(raw_output, Exception):
        err_type = type(raw_output)
        err_msg = str(raw_output)
        
        if issubclass(err_type, (PermissionError, KeyError, ValueError)):
            status = "blocked"
        else:
            status = "failed"
            
        return json.dumps({
            "estado": status,
            "agente": subagent_name,
            "artefacto_generado": None,
            "mensaje": f"Error de ejecución ({err_type.__name__}): {err_msg}"
        }, ensure_ascii=False)

    # 2. Intento de decodificación JSON estructurado
    data_dict: Optional[dict] = None
    text_content = ""

    if isinstance(raw_output, dict):
        data_dict = raw_output
        text_content = json.dumps(raw_output, ensure_ascii=False)
    elif isinstance(raw_output, str):
        text_content = raw_output.strip()
        try:
            parsed = json.loads(text_content)
            if isinstance(parsed, dict):
                data_dict = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # Inspección de esquema estructurado si estuvo disponible
    if data_dict:
        status_val = str(data_dict.get("status", "")).lower()
        if status_val in ("error", "failed", "blocked"):
            err_code = str(data_dict.get("error_code", "")).upper()
            if status_val == "blocked" or err_code in ("MISSING_INPUT", "PERMISSION_DENIED", "BLOCKED"):
                status = "blocked"
            else:
                status = "failed"
            return json.dumps({
                "estado": status,
                "agente": subagent_name,
                "artefacto_generado": None,
                "mensaje": data_dict.get("message", text_content)
            }, ensure_ascii=False)

    # 3. Extracción de Artefactos (IDs de MongoDB de 24 hex o contenido completo) para Ejecución Exitosa
    object_ids = list(set(re.findall(r'\b[a-fA-F0-9]{24}\b', text_content)))

    artefacto = None
    if object_ids:
        if len(object_ids) == 1:
            artefacto = {"id_referencia": object_ids[0]}
        else:
            artefacto = {"ids_referencia": object_ids}
    else:
        artefacto = text_content

    return json.dumps({
        "estado": "success",
        "agente": subagent_name,
        "artefacto_generado": artefacto,
        "mensaje": "Operación completada exitosamente por el subagente."
    }, ensure_ascii=False)
