from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.memory.memory import checkpointer
from core.llm import llm
from core import load_prompt
from agents.school_lesson_plans_agent import agent as lesson_plans_agent
from agents.school_assessment_instruments_agent import agent as assessment_agent
from agents.school_multimodal_resources_agent import agent as multimodal_agent
from agents.specialized_queries_agent import agent as specialized_queries_agent
from middleware.security_middleware import SecurityGuardrailMiddleware


@tool(
    "school_lesson_plans",
    description="Delegates requests related to creating, searching, updating, deleting, or managing school lesson plans (planes de clase) based on CNB."
)
def school_lesson_plans(request: str, config: RunnableConfig) -> str:
    try:
        res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error managing lesson plans: {str(e)}"


@tool(
    "school_assessment_instruments",
    description="Delegates requests related to generating, querying, or managing school assessment instruments (rubrics, checklists, tests, evaluation criteria)."
)
def school_assessment_instruments(request: str, config: RunnableConfig) -> str:
    try:
        res = assessment_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in assessment instruments: {str(e)}"


@tool(
    "school_multimodal_resources",
    description="Delegates requests related to generating, searching, or suggesting educational multimodal resources (videos, images, audio, interactive materials)."
)
def school_multimodal_resources(request: str, config: RunnableConfig) -> str:
    try:
        res = multimodal_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in multimodal resources: {str(e)}"


@tool(
    "specialized_queries",
    description="Delegates requests related to specialized queries about CNB structure, careers, areas, subareas, and frequent courses."
)
def specialized_queries(request: str, config: RunnableConfig) -> str:
    try:
        res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in specialized queries: {str(e)}"


main_agent = create_agent(
    model=llm,
    tools=[
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
