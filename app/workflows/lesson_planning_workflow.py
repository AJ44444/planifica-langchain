import json
import asyncio
from typing import Dict, Any, TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from agents.school_lesson_plans_agent import agent as lesson_plans_agent
from agents.school_assessment_instruments_agent import agent as assessment_agent
from agents.school_multimodal_resources_agent import agent as multimodal_agent


class LessonPlanningState(TypedDict):
    request: str
    plan_output: str
    evaluacion_output: str
    recursos_output: str
    final_output: str


async def node_elaborar_planificacion(state: LessonPlanningState, config: RunnableConfig) -> Dict[str, Any]:
    """
    PASO 1: Elaborar la planificación docente convocando al subagente planificador y esperando su respuesta.
    """
    request = state.get("request", "")
    res = await lesson_plans_agent.ainvoke(
        {"messages": [{"role": "user", "content": request}]},
        config=config
    )
    
    messages = res.get("messages", [])
    plan_text = messages[-1].content if messages else "No se pudo generar la planificación de clase."
    return {"plan_output": plan_text}


async def node_elaborar_recursos_y_evaluacion(state: LessonPlanningState, config: RunnableConfig) -> Dict[str, Any]:
    """
    PASO 2: Elaborar herramientas e instrumentos de evaluación y recursos multimodales EN PARALELO.
    """
    plan_text = state.get("plan_output", "")
    
    eval_prompt = (
        f"Con base en la siguiente planificación docente, elabora los instrumentos de evaluación necesarios (rúbrica o lista de cotejo):\n\n"
        f"{plan_text}"
    )
    rec_prompt = (
        f"Con base en la siguiente planificación docente, busca y genera los recursos educativos multimodales (videos, documentos, imágenes):\n\n"
        f"{plan_text}"
    )

    task_eval = assessment_agent.ainvoke(
        {"messages": [{"role": "user", "content": eval_prompt}]},
        config=config
    )
    task_rec = multimodal_agent.ainvoke(
        {"messages": [{"role": "user", "content": rec_prompt}]},
        config=config
    )

    eval_res, rec_res = await asyncio.gather(task_eval, task_rec, return_exceptions=True)

    eval_text = ""
    if isinstance(eval_res, dict) and "messages" in eval_res and eval_res["messages"]:
        eval_text = eval_res["messages"][-1].content
    elif isinstance(eval_res, Exception):
        eval_text = f"Error al generar instrumentos de evaluación: {str(eval_res)}"

    rec_text = ""
    if isinstance(rec_res, dict) and "messages" in rec_res and rec_res["messages"]:
        rec_text = rec_res["messages"][-1].content
    elif isinstance(rec_res, Exception):
        rec_text = f"Error al generar recursos multimodales: {str(rec_res)}"

    return {
        "evaluacion_output": eval_text,
        "recursos_output": rec_text
    }


async def node_sintetizar_planificacion(state: LessonPlanningState) -> Dict[str, Any]:
    """
    PASO 3: Sintetizar toda la planificación (plan de clase, instrumentos de evaluación y recursos multimodales).
    """
    plan = state.get("plan_output", "")
    evaluacion = state.get("evaluacion_output", "")
    recursos = state.get("recursos_output", "")

    sintesis = {
        "planificacion": plan,
        "instrumentos_evaluacion": evaluacion,
        "recursos_multimodales": recursos
    }
    
    return {"final_output": json.dumps(sintesis, ensure_ascii=False, indent=2)}


# Construcción del StateGraph del Subgrafo de Planificación de Clases
workflow_builder = StateGraph(LessonPlanningState)

workflow_builder.add_node("elaborar_planificacion", node_elaborar_planificacion)
workflow_builder.add_node("elaborar_recursos_y_evaluacion", node_elaborar_recursos_y_evaluacion)
workflow_builder.add_node("sintetizar_planificacion", node_sintetizar_planificacion)

workflow_builder.add_edge(START, "elaborar_planificacion")
workflow_builder.add_edge("elaborar_planificacion", "elaborar_recursos_y_evaluacion")
workflow_builder.add_edge("elaborar_recursos_y_evaluacion", "sintetizar_planificacion")
workflow_builder.add_edge("sintetizar_planificacion", END)

lesson_planning_workflow = workflow_builder.compile()
