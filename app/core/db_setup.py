import os
import logging
from typing import Optional
from .config import REDIS_URI

logger = logging.getLogger(__name__)

_redis_initialized: bool = False


def ensure_redis_connection(redis_uri: Optional[str] = None) -> bool:
    """
    Verifica e inicializa una única vez la conexión con el servidor Redis para streaming/pubsub en LangGraph Server.
    Redis es un almacén clave-valor en memoria (no requiere migración de esquemas); se valida que responda PING.
    """
    global _redis_initialized
    if _redis_initialized:
        return True

    uri = redis_uri or REDIS_URI
    if not uri:
        return False

    try:
        import redis
        client = redis.Redis.from_url(uri, socket_connect_timeout=3)
        client.ping()
        _redis_initialized = True
        logger.info("Conexión con el servidor Redis para LangGraph Server verificada correctamente.")
        return True
    except Exception as e:
        logger.warning(f"No se pudo verificar la conexión con el servidor Redis: {e}")
        return False
