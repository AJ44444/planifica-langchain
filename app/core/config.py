import os
from dotenv import load_dotenv

load_dotenv()


def get_env_variable(var_name: str) -> str:
    value = os.getenv(var_name)
    if value is None or not str(value).strip():
        raise ValueError(f"Environment variable '{var_name}' is not configured in the .env file.")
    return str(value).strip()


DATABASE_URI = os.getenv("DATABASE_URI")
REDIS_URI = os.getenv("REDIS_URI")
LANGGRAPH_AUTH = os.getenv("LANGGRAPH_AUTH")
LANGSERVE_GRAPHS = os.getenv("LANGSERVE_GRAPHS")

LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT")
LANGGRAPH_CLOUD_LICENSE_KEY = os.getenv("LANGGRAPH_CLOUD_LICENSE_KEY")