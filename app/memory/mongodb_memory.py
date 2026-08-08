import logging
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from core.config import DATABASE_URI

logger = logging.getLogger(__name__)


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Retorna el Checkpointer adecuado según el entorno de ejecución:
    - En producción (DATABASE_URI configurada): Instancia PostgresSaver e inicializa automáticamente las tablas de checkpointing y storage con setup().
    - En desarrollo local/pruebas (sin DATABASE_URI): Instancia MemorySaver.
    """
    if DATABASE_URI:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from langgraph.store.postgres import PostgresStore

            # Inicialización de tablas de checkpointing (checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations)
            checkpointer = PostgresSaver.from_conn_string(DATABASE_URI)
            checkpointer.setup()

            # Inicialización de tablas de almacenamiento y vectores (store, store_vectors, store_migrations)
            try:
                store = PostgresStore.from_conn_string(DATABASE_URI)
                store.setup()
            except Exception as store_err:
                logger.warning(f"Advertencia al inicializar PostgresStore: {store_err}")

            logger.info("Checkpointer y Store de PostgreSQL inicializados exitosamente.")
            return checkpointer
        except Exception as e:
            logger.warning(f"No se pudo inicializar PostgresSaver ({e}). Usando MemorySaver como respaldo.")
            return MemorySaver()

    return MemorySaver()


# Instancia global exportada del checkpointer
checkpointer = get_checkpointer()
