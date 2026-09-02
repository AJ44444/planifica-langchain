import re
import json
from typing import Dict, Any, Union, Optional


def validate_subagent_response(subagent_name: str, raw_output: Union[str, dict, Exception]) -> str:
    """
    Valida y estandariza la respuesta de un subagente determinando su estado de ejecución.

    Args:
        subagent_name (str): Nombre identificador del subagente.
        raw_output (Union[str, dict, Exception]): Respuesta cruda, diccionario o excepción retornada por el subagente.

    Returns:
        str: Cadena en formato JSON con el estado de ejecución, nombre del agente, mensaje y artefacto generado.
    """
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
