import logging
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from core.config import DATABASE_URI

logger = logging.getLogger(__name__)


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Retorna el Checkpointer adecuado según el entorno de ejecución:
    - En producción (DATABASE_URI configurada): Instancia PostgresSaver e inicializa automáticamente las tablas con setup().
    - En desarrollo local/pruebas (sin DATABASE_URI): Instancia MemorySaver.
    """
    if DATABASE_URI:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(DATABASE_URI)
            checkpointer.setup()
            logger.info("Checkpointer de PostgreSQL inicializado y tablas configuradas correctamente.")
            return checkpointer
        except Exception as e:
            logger.warning(f"No se pudo inicializar PostgresSaver ({e}). Usando MemorySaver como respaldo.")
            return MemorySaver()

    return MemorySaver()


# Instancia global exportada del checkpointer
checkpointer = get_checkpointer()
