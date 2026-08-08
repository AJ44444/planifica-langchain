import sys
import os

# Asegurar que el directorio app esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.graph import supervisor_graph
from app.auth.auth_handler import auth as google_auth
from app.memory.mongodb_memory import checkpointer
from app.agents.process_pdf_agent import agent as pdf_agent
from app.agents.school_lesson_plans_agent import agent as lesson_plans_agent
from app.agents.school_assessment_instruments_agent import agent as assessment_agent
from app.agents.school_multimodal_resources_agent import agent as multimodal_agent
from app.agents.specialized_queries_agent import agent as queries_agent


def main():
    print("=== Sistema Multiagente Planifica-Langchain (LangGraph Server Production Ready) ===")
    print("[OK] Grafo Supervisor de LangGraph:", supervisor_graph)
    print("     |-- Subagente Procesador de PDF:", pdf_agent)
    print("     |-- Subagente Planificador de Clases:", lesson_plans_agent)
    print("     |-- Subagente de Instrumentos de Evaluacion:", assessment_agent)
    print("     |-- Subagente de Recursos Multimodales:", multimodal_agent)
    print("     +-- Subagente de Consultas Especializadas:", queries_agent)
    print("\n[OK] Checkpointer local de LangGraph:", checkpointer)
    print("[OK] Handler de Autenticacion Google OAuth (langgraph.json):", google_auth)
    print("[OK] Búsqueda de usuarios en MongoDB refactorizada únicamente por 'google_id'.")
    print("El servidor LangGraph Server está listo para producción (PostgreSQL Checkpointing por defecto).")


if __name__ == "__main__":
    main()
