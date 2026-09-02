import json
from typing import Dict, Any, Generator, Optional
from langchain_core.messages import HumanMessage, AIMessage
from agents.main_agent import main_agent, checkpointer

supervisor_graph = main_agent


def run_workflow(query: str, thread_id: str, id_usuario: str = "") -> str:
    """
    Ejecuta una consulta a través del flujo supervisor y sus subagentes.

    Args:
        query (str): Consulta o instrucción del usuario en lenguaje natural.
        thread_id (str): Identificador del hilo de conversación para mantener el contexto.
        id_usuario (str, opcional): Identificador del usuario.

    Returns:
        str: Respuesta textual producida por el supervisor o subagentes.
    """
    config = {"configurable": {"thread_id": thread_id, "id_usuario": id_usuario}}
    initial_input = {"messages": [HumanMessage(content=query)]}

    result = supervisor_graph.invoke(initial_input, config=config)

    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "content"):
            return last_message.content
        elif isinstance(last_message, dict):
            return last_message.get("content", str(last_message))
    return "No se obtuvo respuesta del sistema."


def stream_workflow(query: str, thread_id: str, id_usuario: str = "") -> Generator[Dict[str, Any], None, None]:
    """
    Transmite eventos en tiempo real de la ejecución del flujo del supervisor y sus subagentes.

    Args:
        query (str): Consulta o instrucción del usuario.
        thread_id (str): Identificador del hilo de conversación.
        id_usuario (str, opcional): Identificador del usuario.

    Yields:
        Dict[str, Any]: Eventos transmitidos por el flujo durante la ejecución.
    """
    config = {"configurable": {"thread_id": thread_id, "id_usuario": id_usuario}}
    initial_input = {"messages": [HumanMessage(content=query)]}

    for chunk in supervisor_graph.stream(initial_input, config=config, subgraphs=True):
        yield chunk
