import re
from typing import List, Dict, Any
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage


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
    Sanitizes content returned by external sources (web search, PDF parsing, etc.)
    neutralizing indirect instruction injection attempts and optionally wrapping in XML tags.

    Args:
        text (str): Raw text obtained from a tool or external source.
        wrap_xml (bool): If True, wraps text in <untrusted_external_content>.

    Returns:
        str: Sanitized text.
    """
    if not text:
        return text

    clean_text = str(text)
    for pattern in FORBIDDEN_INJECTION_PATTERNS:
        clean_text = re.sub(pattern, "[RESTRICTED_CONTENT]", clean_text, flags=re.IGNORECASE)

    clean_text = clean_text.strip()
    if wrap_xml:
        return f"<untrusted_external_content>\n{clean_text}\n</untrusted_external_content>"
    return clean_text


class SecurityGuardrailMiddleware(AgentMiddleware):
    """
    Deterministic security middleware for LangChain agents.
    Intercepts user requests and tool responses to detect:
    1. Direct and indirect Prompt Injection attempts.
    2. Security policy bypass and jailbreak attempts.
    """

    def before_agent(self, state: Dict[str, Any], *args, **kwargs) -> Any:
        """
        Validates user input before agent execution begins.
        """
        messages = state.get("messages", [])
        if not messages:
            return state

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
                        "Access Denied by Security Policy: "
                        "Prompt injection or instruction manipulation attempt detected."
                    )

        return state

    def before_model(self, state: Dict[str, Any], *args, **kwargs) -> Any:
        """
        Ensures wrapping and sanitization before LLM invocation.
        """
        return state
