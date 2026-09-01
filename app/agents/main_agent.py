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
    Subagente procesador de PDF del CNB ('procesador_pdf_cnb').
    Analiza un documento PDF escolar para extraer la estructura curricular y guardarla en MongoDB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción enviada al subagente.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
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
    Subagente planificador curricular de clases del CNB ('planificador_clases_cnb').
    Atiende la consulta por ID, actualización o eliminación de planificaciones docentes de clase existentes.
    IMPORTANTE: NO utilizar esta herramienta para elaborar o crear nuevas planificaciones de clase. Toda nueva planificación debe ser elaborada mediante 'complete_lesson_planning_workflow'.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción para consultar por ID, actualizar o eliminar.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
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
    Workflow y Subgrafo de Planificación de Clases del CNB ('lesson_planning_workflow').
    Se invoca SIEMPRE que el docente solicite ELABORAR O CREAR una planificación de clase (diarias, semanales, bimestrales, anuales).
    Ejecuta el flujo en 2 pasos:
    1. Elabora la planificación docente convocando al subagente planificador.
    2. Genera los instrumentos de evaluación y recursos multimodales EN PARALELO y retorna el plan, instrumentos y recursos consolidados.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción con los parámetros clave del plan.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
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
    Subagente diseñador de instrumentos de evaluación del CNB ('instrumentos_evaluacion_cnb').
    Diseña, consulta, actualiza o elimina listas de cotejo, rúbricas y escalas de rango para actividades de aprendizaje.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE gestionar o crear instrumentos de evaluación independientes.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción del docente.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
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
    Subagente de contenidos y recursos multimodales ('recursos_multimodales_cnb').
    Busca recursos educativos en la web (videos, imágenes, documentos) con SERPER API y gestiona su almacenamiento.
    Usa esta herramienta cuando el docente solicite ÚNICAMENTE buscar o gestionar recursos multimodales independientes.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción del docente.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
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
    Subagente de consultas especializadas y métricas del dashboard ('consultas_especializadas_cnb').
    Atiende consultas del panel del docente (top cursos, recientes), historial paginado de planificaciones, detalles completos de planes y catálogo del CNB.
    Propaga la configuración de contexto y autenticación de LangGraph.
    
    Args:
        request: Instrucción del docente.
        config: Objeto de configuración de estado y autenticación de LangGraph.
        
    Returns:
        Resultado validado determinísticamente con estado y artefacto generado.
    """
    try:
        res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        raw_output = res["messages"][-1].content if res.get("messages") else "No se obtuvo respuesta."
        return validate_subagent_response("consultas_especializadas_cnb", raw_output)
    except Exception as e:
        return validate_subagent_response("consultas_especializadas_cnb", e)


# Agente Supervisor Principal de LangGraph equipado con checkpointer MongoDBSaver respaldado por MongoDB
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
