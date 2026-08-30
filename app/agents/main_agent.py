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
from core.tool_inputs import SubagentCallInput


def _sanitize_request_limit(request: str, max_chars: int = 300) -> str:
    """Garantiza que la request entregada al subagente cumpla el estándar de máximo 300 caracteres."""
    req_clean = request.strip()
    return req_clean[:max_chars] if len(req_clean) > max_chars else req_clean


@tool("call_process_pdf_agent", args_schema=SubagentCallInput, return_direct=True)
def call_process_pdf_agent(request: str, config: RunnableConfig) -> str:
    """
    Analiza un documento PDF escolar para extraer la estructura curricular y guardarla en MongoDB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa de máximo 300 caracteres.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con el resultado del subagente procesador de PDF.
    """
    clean_req = _sanitize_request_limit(request)
    res = pdf_agent.invoke({"messages": [{"role": "user", "content": clean_req}]}, config=config)
    return res["messages"][-1].content


@tool("call_school_lesson_plans_agent", args_schema=SubagentCallInput, return_direct=True)
def call_school_lesson_plans_agent(request: str, config: RunnableConfig) -> str:
    """
    Atiende la consulta por ID, actualización o eliminación de planificaciones docentes de clase existentes.
    IMPORTANTE: NO utilizar esta herramienta para elaborar o crear nuevas planificaciones de clase. Toda nueva planificación debe ser elaborada mediante 'call_complete_lesson_planning_workflow'.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa para consultar por ID, actualizar o eliminar.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta del subagente planificador.
    """
    clean_req = _sanitize_request_limit(request)
    res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": clean_req}]}, config=config)
    return res["messages"][-1].content


@tool("call_complete_lesson_planning_workflow", args_schema=SubagentCallInput, return_direct=True)
async def call_complete_lesson_planning_workflow(request: str, config: RunnableConfig) -> str:
    """
    Workflow de Planificación de Clases del CNB ('lesson_planning_workflow').
    Se invoca si el docente solicita ELABORAR O CREAR una planificación de clase (diarias, semanales, bimestrales, anuales).
    Ejecuta el flujo completo de 4 pasos:
    1. Elabora la planificación docente convocando al subagente planificador.
    2. Genera los instrumentos de evaluación y recursos multimodales EN PARALELO.
    3. Sintetiza toda la planificación.
    4. Entrega el resultado final consolidado.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa con los parámetros clave del plan.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con la planificación completa sintetizada (plan, evaluación y recursos).
    """
    clean_req = _sanitize_request_limit(request)
    res = await lesson_planning_workflow.ainvoke({"request": clean_req}, config=config)
    return res.get("final_output", "No se obtuvo respuesta del workflow de planificación completa.")


@tool("call_school_assessment_instruments_agent", args_schema=SubagentCallInput, return_direct=True)
def call_school_assessment_instruments_agent(request: str, config: RunnableConfig) -> str:
    """
    Diseña, consulta, actualiza o elimina listas de cotejo, rúbricas y escalas de rango para actividades de aprendizaje.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE gestionar o crear instrumentos de evaluación independientes.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con el instrumento generado o resultado de la gestión.
    """
    clean_req = _sanitize_request_limit(request)
    res = assessment_agent.invoke({"messages": [{"role": "user", "content": clean_req}]}, config=config)
    return res["messages"][-1].content


@tool("call_school_multimodal_resources_agent", args_schema=SubagentCallInput, return_direct=True)
def call_school_multimodal_resources_agent(request: str, config: RunnableConfig) -> str:
    """
    Busca recursos educativos en la web (videos, imágenes, documentos) y gestiona su almacenamiento.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE buscar o gestionar recursos multimodales independientes.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con los recursos encontrados o resultado de la operación.
    """
    clean_req = _sanitize_request_limit(request)
    res = multimodal_agent.invoke({"messages": [{"role": "user", "content": clean_req}]}, config=config)
    return res["messages"][-1].content


@tool("call_specialized_queries_agent", args_schema=SubagentCallInput, return_direct=True)
def call_specialized_queries_agent(request: str, config: RunnableConfig) -> str:
    """
    Atiende consultas del panel del docente (top cursos, recientes), historial paginado de planificaciones, detalles completos de planes y catálogo del CNB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción limpia y concisa de máximo 300 caracteres.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Respuesta con los datos analíticos o resultados de la consulta especializada.
    """
    clean_req = _sanitize_request_limit(request)
    res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": clean_req}]}, config=config)
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
