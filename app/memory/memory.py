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
    if DATABASE_URI:
        try:
            pool = ConnectionPool(
                conninfo=DATABASE_URI,
                max_size=20,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
            )
            checkpointer = PostgresSaver(pool)
            checkpointer.setup()
            PostgresStore(pool).setup()
            logger.info("PostgreSQL Checkpointer successfully initialized.")
            return checkpointer
        except Exception as e:
            logger.warning(f"Could not initialize PostgresSaver ({e}). Using MemorySaver.")

    return MemorySaver()


checkpointer = get_checkpointer()
