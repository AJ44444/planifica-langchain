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
    final_output: str


def _get_isolated_subagent_config(config: RunnableConfig, subagent_name: str) -> RunnableConfig:
    """
    Genera un espacio de nombres aislado para la ejecución del subagente.

    Args:
        config (RunnableConfig): Configuración de ejecución actual.
        subagent_name (str): Nombre del subagente.

    Returns:
        RunnableConfig: Configuración con el espacio de nombres asignado.
    """
    if not config:
        return {}
    cfg = dict(config)
    configurable = dict(cfg.get("configurable", {}))
    parent_ns = configurable.get("checkpoint_ns", "")
    configurable["checkpoint_ns"] = f"{parent_ns}:{subagent_name}" if parent_ns else subagent_name
    cfg["configurable"] = configurable
    return cfg


async def node_elaborar_planificacion(state: LessonPlanningState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Elabora la planificación docente inicial convocando al subagente planificador.

    Args:
        state (LessonPlanningState): Estado actual del flujo de planificación.
        config (RunnableConfig): Configuración de ejecución.

    Returns:
        Dict[str, Any]: Diccionario con la planificación docente generada en 'plan_output'.
    """
    request = state.get("request", "")
    plan_config = _get_isolated_subagent_config(config, "plan_agent")
    res = await lesson_plans_agent.ainvoke(
        {"messages": [{"role": "user", "content": request.strip()}]},
        config=plan_config
    )

    messages = res.get("messages", [])
    plan_text = messages[-1].content if messages else "No se pudo generar la planificación de clase."
    return {"plan_output": plan_text}


async def node_elaborar_recursos_y_evaluacion(state: LessonPlanningState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Genera en paralelo los instrumentos de evaluación y recursos multimodales consolidados.

    Args:
        state (LessonPlanningState): Estado actual con la planificación elaborada.
        config (RunnableConfig): Configuración de ejecución.

    Returns:
        Dict[str, Any]: Diccionario con la salida final consolidada en 'final_output'.
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

    eval_config = _get_isolated_subagent_config(config, "eval_agent")
    rec_config = _get_isolated_subagent_config(config, "rec_agent")

    task_eval = assessment_agent.ainvoke(
        {"messages": [{"role": "user", "content": eval_prompt}]},
        config=eval_config
    )
    task_rec = multimodal_agent.ainvoke(
        {"messages": [{"role": "user", "content": rec_prompt}]},
        config=rec_config
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

    resultado_consolidado = {
        "planificacion": plan_text,
        "instrumentos_evaluacion": eval_text,
        "recursos_multimodales": rec_text
    }

    return {
        "final_output": json.dumps(resultado_consolidado, ensure_ascii=False, indent=2)
    }


workflow_builder = StateGraph(LessonPlanningState)

workflow_builder.add_node("elaborar_planificacion", node_elaborar_planificacion)
workflow_builder.add_node("elaborar_recursos_y_evaluacion", node_elaborar_recursos_y_evaluacion)

workflow_builder.add_edge(START, "elaborar_planificacion")
workflow_builder.add_edge("elaborar_planificacion", "elaborar_recursos_y_evaluacion")
workflow_builder.add_edge("elaborar_recursos_y_evaluacion", END)

lesson_planning_workflow = workflow_builder.compile()
