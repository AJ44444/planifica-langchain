from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from memory.mongodb_memory import checkpointer
from core.llm import llm
from prompts.system_prompts import SYSTEM_PROMPT_SUPERVISOR
from agents.process_pdf_agent import agent as pdf_agent
from agents.school_lesson_plans_agent import agent as lesson_plans_agent
from agents.school_assessment_instruments_agent import agent as assessment_agent
from agents.school_multimodal_resources_agent import agent as multimodal_agent
from agents.specialized_queries_agent import agent as specialized_queries_agent
from middleware.security_middleware import SecurityGuardrailMiddleware
from workflows.lesson_planning_workflow import lesson_planning_workflow
from core.validator import validate_subagent_response


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
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("procesador_pdf_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("procesador_pdf_cnb", e)


@tool("school_lesson_plans")
def school_lesson_plans(request: str, config: RunnableConfig) -> str:
    """
    Gestiona la consulta por ID, actualización o eliminación de planificaciones de clase existentes.

    Args:
        request (str): Instrucción para consultar, actualizar o eliminar planificaciones.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Resultado de la gestión de la planificación solicitada.
    """
    try:
        res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("planificador_clases_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("planificador_clases_cnb", e)


@tool("complete_lesson_planning_workflow")
async def complete_lesson_planning_workflow(request: str, config: RunnableConfig) -> str:
    """
    Ejecuta el flujo completo para crear y elaborar nuevas planificaciones docentes con instrumentos y recursos.

    Args:
        request (str): Instrucción con los requerimientos y parámetros clave del plan a crear.
        config (RunnableConfig): Configuración de ejecución y contexto de LangGraph.

    Returns:
        str: Planificación completa elaborada junto a sus instrumentos de evaluación y recursos multimodales.
    """
    try:
        res = await lesson_planning_workflow.ainvoke({"request": request.strip()}, config=config)
        raw_output = res.get("final_output", "No se obtuvo respuesta del workflow de planificación completa.")
        return validate_subagent_response("lesson_planning_workflow", raw_output)
    except Exception as e:
        return validate_subagent_response("lesson_planning_workflow", e)


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
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("instrumentos_evaluacion_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("instrumentos_evaluacion_cnb", e)


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
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("recursos_multimodales_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("recursos_multimodales_cnb", e)


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
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("consultas_especializadas_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("consultas_especializadas_cnb", e)


main_agent = create_agent(
    model=llm,
    tools=[
        process_pdf,
        school_lesson_plans,
        complete_lesson_planning_workflow,
        school_assessment_instruments,
        school_multimodal_resources,
        specialized_queries
    ],
    system_prompt=SYSTEM_PROMPT_SUPERVISOR,
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
