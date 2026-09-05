"""
Sub-agent responsible for searching and managing multimodal resources.
"""
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.web_search_tool import serper_web_search
from tools.persistence_tool import (
    save_multimodal_resource,
    get_multimodal_resource_by_id,
    update_multimodal_resource,
    delete_multimodal_resource,
    get_learning_activity_by_id
)
from middleware.security_middleware import SecurityGuardrailMiddleware
from core import load_prompt

agent = create_agent(
    model=llm,
    tools=[
        get_learning_activity_by_id,
        serper_web_search,
        save_multimodal_resource,
        get_multimodal_resource_by_id,
        update_multimodal_resource,
        delete_multimodal_resource
    ],
    system_prompt=load_prompt("school_multimodal_resources.md"),
    name="recursos_multimodales_cnb",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
