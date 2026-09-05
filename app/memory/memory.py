import logging
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from core.config import DATABASE_URI
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

logger = logging.getLogger(__name__)


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Retorna el Checkpointer adecuado según el entorno de ejecución:
    - En producción (DATABASE_URI configurada): Instancia PostgresSaver e inicializa automáticamente las tablas de checkpointing y storage con setup().
    - En desarrollo local/pruebas (sin DATABASE_URI): Instancia MemorySaver.
    """
    if DATABASE_URI:
        try:
            pool = ConnectionPool(
                conninfo=DATABASE_URI,
                max_size=20,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
            )

            checkpointer = PostgresSaver(pool)
            checkpointer.setup()

            try:
                store = PostgresStore(pool)
                store.setup()
            except Exception as store_err:
                logger.warning(f"Advertencia al inicializar PostgresStore: {store_err}")

            logger.info("Checkpointer y Store de PostgreSQL inicializados exitosamente.")
            return checkpointer
        except Exception as e:
            logger.warning(f"No se pudo inicializar PostgresSaver ({e}). Usando MemorySaver como respaldo.")
            return MemorySaver()

    return MemorySaver()


checkpointer = get_checkpointer()
