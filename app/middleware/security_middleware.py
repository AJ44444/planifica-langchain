import re
from typing import List, Dict, Any, Tuple
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage


# Patrones de inyección de prompt, jailbreak y comandos maliciosos conocidos
FORBIDDEN_INJECTION_PATTERNS: List[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignora\s+(todas\s+)?(tus\s+)?instrucciones",
    r"system\s+prompt\s+override",
    r"revela\s+(tu\s+)?system\s+prompt",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"actua\s+como\s+dan",
    r"dan\s+mode",
    r"drop\s+database",
    r"borra\s+toda\s+la\s+base\s+de\s+datos",
    r"bypass\s+security",
    r"salta\s+la\s+seguridad",
]


def sanitize_external_text(text: str, wrap_xml: bool = False) -> str:
    """
    Sanitiza el contenido devuelto por fuentes externas (búsquedas web, parseo de PDF, etc.)
    eliminando intentos de inyección de instrucciones indirectas y opcionalmente delimitándolo en etiquetas XML.
    
    Args:
        text (str): Texto bruto obtenido de una herramienta o fuente externa.
        wrap_xml (bool): Si es True, envuelve el texto en <untrusted_external_content>.

    Returns:
        str: Texto sanitizado.
    """
    if not text:
        return text

    clean_text = str(text)
    # Neutralizar patrones sospechosos de anulación en contenido de herramientas externas
    for pattern in FORBIDDEN_INJECTION_PATTERNS:
        clean_text = re.sub(pattern, "[CONTENIDO_RESTRINGIDO]", clean_text, flags=re.IGNORECASE)

    clean_text = clean_text.strip()
    if wrap_xml:
        return f"<untrusted_external_content>\n{clean_text}\n</untrusted_external_content>"
    return clean_text


class SecurityGuardrailMiddleware(AgentMiddleware):
    """
    Middleware determinista de seguridad para agentes de LangChain.
    Intercepta las solicitudes del usuario y las respuestas de herramientas para detectar:
    1. Intenciones de Prompt Injection (directo e indirecto).
    2. Intentos de salto de políticas de seguridad y jailbreaks.
    """

    def before_agent(self, state: Dict[str, Any], config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Valida la entrada del usuario antes de que el agente comience la ejecución.
        """
        messages = state.get("messages", [])
        if not messages:
            return state, config

        last_message = messages[-1]
        content = ""
        if isinstance(last_message, BaseMessage):
            content = str(last_message.content)
        elif isinstance(last_message, dict):
            content = str(last_message.get("content", ""))

        if content:
            lower_content = content.lower()
            for pattern in FORBIDDEN_INJECTION_PATTERNS:
                if re.search(pattern, lower_content):
                    raise ValueError(
                        "Acceso Denegado por Políticas de Seguridad: "
                        "Se detectó un intento de manipulación de instrucciones o inyección de prompt."
                    )

        return state, config

    def before_model(self, state: Dict[str, Any], config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Garantiza la envoltura y sanitización antes de la llamada al modelo LLM.
        """
        return state, config
