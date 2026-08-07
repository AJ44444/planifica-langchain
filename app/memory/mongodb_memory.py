import os
from typing import Union
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from core.config import DB, DB_NAME
from core.collections import CHECKPOINTS, CHECKPOINT_WRITES
from tools.persistence_tool import get_mongo_client


def setup_checkpoint_indexes(client, db_name: str) -> None:
    """
    Crea automáticamente los índices necesarios en las colecciones 'checkpoints' y 'checkpoint_writes'
    de MongoDB para la persistencia eficiente de estados e hilos de LangGraph Server.
    """
    try:
        db = client[db_name]
        
        # 1. Índice compuesto para la colección 'checkpoints'
        checkpoints_col = db[CHECKPOINTS]
        checkpoints_col.create_index(
            [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", -1)],
            name="idx_checkpoint_lookup"
        )
        
        # 2. Índice compuesto para la colección 'checkpoint_writes'
        writes_col = db[CHECKPOINT_WRITES]
        writes_col.create_index(
            [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", 1), ("task_id", 1), ("idx", 1)],
            name="idx_writes_lookup"
        )
    except Exception as e:
        print(f"[WARN] No se pudieron crear automáticamente los índices de checkpoints en MongoDB: {str(e)}")


def get_mongodb_checkpointer() -> BaseCheckpointSaver:
    """
    Retorna el Checkpointer persistente respaldado por MongoDB (MongoDBSaver) para la memoria
    a corto plazo y la persistencia multi-turno de LangGraph en producción.
    Crea automáticamente los índices requeridos en las colecciones checkpoints y checkpoint_writes.
    Si DB_URI no está configurada, utiliza MemorySaver en memoria de forma segura.
    """
    if DB:
        try:
            client = get_mongo_client()
            db_name = DB_NAME or "planifica_db"

            # Crear índices automáticamente si no existen
            setup_checkpoint_indexes(client, db_name)

            return MongoDBSaver(
                client=client,
                db_name=db_name,
                checkpoint_collection_name=CHECKPOINTS,
                writes_collection_name=CHECKPOINT_WRITES
            )
        except Exception as e:
            print(f"[WARN] No se pudo conectar MongoDBSaver, usando MemorySaver en memoria fallback: {str(e)}")
            return MemorySaver()
    else:
        return MemorySaver()


# Instancia global exportada del checkpointer respaldado en MongoDB
checkpointer = get_mongodb_checkpointer()
