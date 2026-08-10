from langchain.agents import create_agent
from core.llm import llm
from tools.web_search_tool import serper_web_search
from tools.persistence_tool import (
    save_multimodal_resource,
    get_multimodal_resource_by_id,
    update_multimodal_resource,
    delete_multimodal_resource,
    get_recent_lesson_plans,
    get_paginated_lesson_plans,
    get_full_lesson_plan_details,
    get_latest_plan_instruments_and_resources
)
from prompts.system_prompts import SYSTEM_PROMPT_SCHOOL_MULTIMODAL_RESOURCES

agent = create_agent(
    model=llm,
    tools=[
        serper_web_search,
        save_multimodal_resource,
        get_multimodal_resource_by_id,
        update_multimodal_resource,
        delete_multimodal_resource,
        get_recent_lesson_plans,
        get_paginated_lesson_plans,
        get_full_lesson_plan_details,
        get_latest_plan_instruments_and_resources
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_MULTIMODAL_RESOURCES
)
