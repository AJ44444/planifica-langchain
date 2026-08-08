import json
from typing import Dict, Any, Generator, Optional
from langchain_core.messages import HumanMessage, AIMessage
from agents.main_agent import main_agent, checkpointer
from core.db_setup import ensure_postgres_tables, ensure_redis_connection

# Inicialización y verificación preventiva de PostgreSQL y Redis al cargar el módulo en producción
ensure_postgres_tables()
ensure_redis_connection()

# Grafo Supervisor Principal Compilado con Checkpointer en main_agent.py
supervisor_graph = main_agent


def run_workflow(query: str, thread_id: str = "default_thread", id_usuario: str = "") -> str:
    """
    Ejecuta una consulta a través del workflow LangGraph del Agente Supervisor Principal,
    preservando el estado y la memoria a corto plazo del hilo de conversación.
    
    Args:
        query: Consulta o instrucción del usuario en lenguaje natural.
        thread_id: ID del hilo de conversación para mantener el contexto persistente.
        id_usuario: ID opcional del usuario en MongoDB.
        
    Returns:
        Respuesta textual producida por el supervisor o subagentes activados.
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


def stream_workflow(query: str, thread_id: str = "default_thread", id_usuario: str = "") -> Generator[Dict[str, Any], None, None]:
    """
    Transmite en tiempo real los eventos de ejecución del grafo y subgrafos (subagentes).
    
    Args:
        query: Consulta o instrucción del usuario.
        thread_id: ID del hilo de conversación.
        id_usuario: ID del usuario.
        
    Yields:
        Eventos transmitidos por el flujo de LangGraph.
    """
    config = {"configurable": {"thread_id": thread_id, "id_usuario": id_usuario}}
    initial_input = {"messages": [HumanMessage(content=query)]}

    for chunk in supervisor_graph.stream(initial_input, config=config, subgraphs=True):
        yield chunk
