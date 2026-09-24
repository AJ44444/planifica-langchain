import json
from typing import Dict, Any, Generator, Optional
from langchain_core.messages import HumanMessage, AIMessage
from agents.main_agent import main_agent, checkpointer

supervisor_graph = main_agent


def run_workflow(query: str, thread_id: str, id_usuario: str = "") -> str:
    config = {"configurable": {"thread_id": thread_id, "id_usuario": id_usuario}}
    initial_input = {"messages": [HumanMessage(content=query)]}

    result = supervisor_graph.invoke(initial_input, config=config)

    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "content"):
            return last_message.content
        elif isinstance(last_message, dict):
            return last_message.get("content", str(last_message))
    return "No response obtained from the system."


def stream_workflow(query: str, thread_id: str, id_usuario: str = "") -> Generator[Dict[str, Any], None, None]:
    config = {"configurable": {"thread_id": thread_id, "id_usuario": id_usuario}}
    initial_input = {"messages": [HumanMessage(content=query)]}

    for chunk in supervisor_graph.stream(initial_input, config=config, subgraphs=True):
        yield chunk
