import os
from dotenv import load_dotenv

load_dotenv()


def get_env_variable(var_name: str) -> str:
    """
    Obtiene y valida el valor de una variable de entorno.
    Si la variable está configurada, retorna su valor.
    Si no está configurada, lanza un ValueError indicando que la variable de entorno no está configurada.
    """
    value = os.getenv(var_name)
    if value is None or not str(value).strip():
        raise ValueError(f"La variable de entorno '{var_name}' no está configurada en el archivo .env.")
    return str(value).strip()


# Variables opcionales de producción para PostgreSQL, Redis y LangGraph Server
DATABASE_URI = os.getenv("DATABASE_URI")
REDIS_URI = os.getenv("REDIS_URI")
LANGGRAPH_AUTH = os.getenv("LANGGRAPH_AUTH")
LANGSERVE_GRAPHS = os.getenv("LANGSERVE_GRAPHS")

# Licencia, Tracing y Observabilidad de LangSmith / LangGraph Server
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT")
LANGGRAPH_CLOUD_LICENSE_KEY = os.getenv("LANGGRAPH_CLOUD_LICENSE_KEY")