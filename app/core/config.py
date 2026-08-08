import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")
GOOGLE = os.getenv("GOOGLE_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME")
SERPER = os.getenv("SERPER_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

# Variables de entorno de producción para PostgreSQL, Redis y LangGraph Server
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