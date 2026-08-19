from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.web_search_tool import serper_web_search
from tools.persistence_tool import (
    save_multimodal_resource,
    get_multimodal_resource_by_id,
    update_multimodal_resource,
    delete_multimodal_resource,
    get_paginated_lesson_plans,
    get_full_lesson_plan_details
)
from middleware.security_middleware import SecurityGuardrailMiddleware
from prompts.system_prompts import SYSTEM_PROMPT_SCHOOL_MULTIMODAL_RESOURCES

agent = create_agent(
    model=llm,
    tools=[
        serper_web_search,
        save_multimodal_resource,
        get_multimodal_resource_by_id,
        update_multimodal_resource,
        delete_multimodal_resource,
        get_paginated_lesson_plans,
        get_full_lesson_plan_details
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_MULTIMODAL_RESOURCES,
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
