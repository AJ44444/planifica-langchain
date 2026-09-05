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
    Returns the appropriate Checkpointer based on the execution environment:
    - In production (DATABASE_URI configured): Instantiates PostgresSaver and automatically initializes checkpointing and storage tables with setup().
    - In local development/testing (without DATABASE_URI): Instantiates MemorySaver.
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
                logger.warning(f"Warning initializing PostgresStore: {store_err}")

            logger.info("PostgreSQL Checkpointer and Store successfully initialized.")
            return checkpointer
        except Exception as e:
            logger.warning(f"Could not initialize PostgresSaver ({e}). Using MemorySaver as fallback.")
            return MemorySaver()

    return MemorySaver()


checkpointer = get_checkpointer()
