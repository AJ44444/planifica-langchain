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


@tool(return_direct=True)
def call_process_pdf_agent(request: str, config: RunnableConfig) -> str:
    """
    Subagente procesador de PDF del CNB.
    Analiza un documento PDF escolar para extraer la estructura curricular y guardarla en MongoDB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción o parámetros para procesar el documento PDF.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con el resultado del subagente procesador de PDF.
    """
    res = pdf_agent.invoke({"messages": [{"role": "user", "content": request}]}, config=config)
    return res["messages"][-1].content


@tool(return_direct=True)
def call_school_lesson_plans_agent(request: str, config: RunnableConfig) -> str:
    """
    Subagente planificador curricular de clases del CNB.
    Elabora, consulta, actualiza o elimina planificaciones docentes de clase individuales (diarias, semanales, bimestrales).
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE elaborar o gestionar una planificación de clase.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Solicitud o instrucción para la planificación de clase.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con la planificación o resultado del subagente planificador.
    """
    res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": request}]}, config=config)
    return res["messages"][-1].content


@tool(return_direct=True)
async def call_complete_lesson_planning_workflow(request: str, config: RunnableConfig) -> str:
    """
    Workflow y Subgrafo de Planificación COMPLETA de Clases del CNB.
    Se invoca ÚNICAMENTE cuando el docente solicita una PLANIFICACIÓN COMPLETA (que incluye la planificación de clase, instrumentos de evaluación y recursos multimodales).
    Ejecuta el flujo de 4 pasos:
    1. Elabora la planificación docente.
    2. Genera los instrumentos de evaluación y recursos multimodales EN PARALELO.
    3. Sintetiza toda la planificación.
    4. Entrega el resultado final consolidado.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Solicitud para la planificación completa de clase.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con la planificación completa sintetizada (plan, evaluación y recursos).
    """
    res = await lesson_planning_workflow.ainvoke({"request": request}, config=config)
    return res.get("final_output", "No se obtuvo respuesta del workflow de planificación completa.")


@tool(return_direct=True)
def call_school_assessment_instruments_agent(request: str, config: RunnableConfig) -> str:
    """
    Subagente diseñador de instrumentos de evaluación del CNB.
    Diseña, consulta, actualiza o elimina listas de cotejo, rúbricas y escalas de rango para actividades de aprendizaje.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE gestionar o crear instrumentos de evaluación.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Solicitud para crear o gestionar instrumentos de evaluación.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con el instrumento generado o resultado de la gestión.
    """
    res = assessment_agent.invoke({"messages": [{"role": "user", "content": request}]}, config=config)
    return res["messages"][-1].content


@tool(return_direct=True)
def call_school_multimodal_resources_agent(request: str, config: RunnableConfig) -> str:
    """
    Subagente de contenidos y recursos multimodales.
    Busca recursos educativos en la web (videos, imágenes, documentos) con SERPER API y gestiona su almacenamiento.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE buscar o gestionar recursos multimodales.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Solicitud para buscar o administrar recursos multimodales.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con los recursos encontrados o resultado de la operación.
    """
    res = multimodal_agent.invoke({"messages": [{"role": "user", "content": request}]}, config=config)
    return res["messages"][-1].content


@tool(return_direct=True)
def call_specialized_queries_agent(request: str, config: RunnableConfig) -> str:
    """
    Subagente de consultas especializadas y métricas del dashboard.
    Atiende consultas del panel del docente (top cursos, recientes), historial paginado de planificaciones, detalles completos de planes y catálogo del CNB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Consulta o reporte solicitado.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con los datos analíticos o resultados de la consulta especializada.
    """
    res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": request}]}, config=config)
    return res["messages"][-1].content


# Agente Supervisor Principal de LangGraph equipado con checkpointer MongoDBSaver respaldado por MongoDB
main_agent = create_agent(
    model=llm,
    tools=[
        call_process_pdf_agent,
        call_school_lesson_plans_agent,
        call_complete_lesson_planning_workflow,
        call_school_assessment_instruments_agent,
        call_school_multimodal_resources_agent,
        call_specialized_queries_agent
    ],
    system_prompt=SYSTEM_PROMPT_SUPERVISOR,
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
