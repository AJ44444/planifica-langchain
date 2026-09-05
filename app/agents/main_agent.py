from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.memory.memory import checkpointer
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
    Processes and analyzes school PDF documents to extract their curricular structure.

    Args:
        request (str): Instruction containing details of the PDF document to process.
        config (RunnableConfig): Execution configuration and LangGraph context.

    Returns:
        str: Processing result containing status and extracted curricular structure.
    """
    try:
        res = pdf_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error processing PDF: {str(e)}"


@tool("school_lesson_plans")
def school_lesson_plans(request: str, config: RunnableConfig) -> str:
    """
    Manages creation, query by ID, updating, or deletion of lesson plans.

    Args:
        request (str): Instruction to create, query, update, or delete lesson plans.
        config (RunnableConfig): Execution configuration and LangGraph context.

    Returns:
        str: Result of the requested lesson plan management operation.
    """
    try:
        res = lesson_plans_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error managing lesson plans: {str(e)}"


@tool("school_assessment_instruments")
def school_assessment_instruments(request: str, config: RunnableConfig) -> str:
    """
    Designs, queries, updates, or deletes independent assessment instruments (rubrics, checklists, rating scales).

    Args:
        request (str): Instruction with details of the assessment instrument to manage or create.
        config (RunnableConfig): Execution configuration and LangGraph context.

    Returns:
        str: Result with information about the processed assessment instrument.
    """
    try:
        res = assessment_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in assessment instruments: {str(e)}"


@tool("school_multimodal_resources")
def school_multimodal_resources(request: str, config: RunnableConfig) -> str:
    """
    Searches, queries, updates, or deletes independent multimodal resources (videos, documents, images).

    Args:
        request (str): Instruction with resource requirements to search or manage.
        config (RunnableConfig): Execution configuration and LangGraph context.

    Returns:
        str: Result with found or processed multimodal resources.
    """
    try:
        res = multimodal_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in multimodal resources: {str(e)}"


@tool("specialized_queries")
def specialized_queries(request: str, config: RunnableConfig) -> str:
    """
    Handles teacher dashboard queries, metrics, CNB catalog, and paginated lesson plan history.

    Args:
        request (str): Instruction or query regarding catalog or metrics.
        config (RunnableConfig): Execution configuration and LangGraph context.

    Returns:
        str: Detailed response to the requested query.
    """
    try:
        res = specialized_queries_agent.invoke({"messages": [{"role": "user", "content": request.strip()}]}, config=config)
        return res["messages"][-1].content if res.get("messages") else "No response obtained."
    except Exception as e:
        return f"Error in specialized queries: {str(e)}"


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
