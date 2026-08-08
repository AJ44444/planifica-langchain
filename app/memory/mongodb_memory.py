from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Retorna el Checkpointer local (MemorySaver) para pruebas y desarrollo en memoria.
    En producción, LangGraph Server gestiona automáticamente la persistencia de hilos
    y estados utilizando PostgreSQL.
    """
    return MemorySaver()


# Instancia global exportada del checkpointer en memoria
checkpointer = get_checkpointer()
