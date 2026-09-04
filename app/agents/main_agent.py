from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from memory.mongodb_memory import checkpointer
from core.llm import llm
from core import load_prompt
from agents.process_pdf_agent import agent as pdf_agent
from agents.school_lesson_plans_agent import agent as lesson_plans_agent
from agents.school_assessment_instruments_agent import agent as assessment_agent
from agents.school_multimodal_resources_agent import agent as multimodal_agent
from agents.specialized_queries_agent import agent as specialized_queries_agent
from middleware.security_middleware import SecurityGuardrailMiddleware


@tool("process_pdf")
def process_pdf(request: str, config: RunnableConfig) -> str:
    """
    Procesa y analiza documentos PDF escolares para extraer su estructura curricular.

    Args:
        request (str): Instrucción con los datos del documento PDF a procesar.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Resultado del procesamiento con el estado y la estructura curricular extraída.
    """
    try:
        res = pdf_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
    except Exception as e:
        return f"Error al procesar PDF: {str(e)}"


@tool("school_lesson_plans")
def school_lesson_plans(request: str, config: RunnableConfig) -> str:
    """
    Gestiona la creación, consulta por ID, actualización o eliminación de planificaciones de clase.

    Args:
        request (str): Instrucción para crear, consultar, actualizar o eliminar planificaciones.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Resultado de la gestión de la planificación solicitada.
    """
    try:
        res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
    except Exception as e:
        return f"Error en gestión de planificaciones: {str(e)}"


@tool("school_assessment_instruments")
def school_assessment_instruments(request: str, config: RunnableConfig) -> str:
    """
    Diseña, consulta, actualiza o elimina instrumentos de evaluación independientes (rúbricas, listas de cotejo).

    Args:
        request (str): Instrucción con los detalles del instrumento a gestionar o crear.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Resultado con la información del instrumento de evaluación procesado.
    """
    try:
        res = assessment_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
    except Exception as e:
        return f"Error en instrumentos de evaluación: {str(e)}"


@tool("school_multimodal_resources")
def school_multimodal_resources(request: str, config: RunnableConfig) -> str:
    """
    Busca, consulta, actualiza o elimina recursos multimodales independientes (videos, documentos, imágenes).

    Args:
        request (str): Instrucción con los requerimientos del recurso a buscar o gestionar.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Resultado con los recursos multimodales encontrados o procesados.
    """
    try:
        res = multimodal_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
    except Exception as e:
        return f"Error en recursos multimodales: {str(e)}"


@tool("specialized_queries")
def specialized_queries(request: str, config: RunnableConfig) -> str:
    """
    Atiende consultas del panel docente, métricas, catálogo del CNB e historial paginado de planificaciones.

    Args:
        request (str): Instrucción o consulta a realizar sobre el catálogo o métricas.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Respuesta detallada a la consulta solicitada.
    """
    try:
        res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
    except Exception as e:
        return f"Error en consultas especializadas: {str(e)}"


main_agent = create_agent(
    model=llm,
    tools=[
        process_pdf,
        school_lesson_plans,
        school_assessment_instruments,
        school_multimodal_resources,
        specialized_queries
    ],
    system_prompt=load_prompt("supervisor.md"),
    name="supervisor_planifica",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ],
    checkpointer=checkpointer
)
