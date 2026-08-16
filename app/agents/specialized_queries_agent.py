from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.persistence_tool import (
    get_top_frequent_courses,
    get_recent_lesson_plans,
    get_latest_plan_instruments_and_resources,
    get_paginated_lesson_plans,
    get_full_lesson_plan_details,
    get_cnb_careers_list,
    get_cnb_areas_by_career,
    get_cnb_subareas_by_area_id,
    get_cnb_subarea_by_id
)
from prompts.system_prompts import SYSTEM_PROMPT_SPECIALIZED_QUERIES

agent = create_agent(
    model=llm,
    tools=[
        get_top_frequent_courses,
        get_recent_lesson_plans,
        get_latest_plan_instruments_and_resources,
        get_paginated_lesson_plans,
        get_full_lesson_plan_details,
        get_cnb_careers_list,
        get_cnb_areas_by_career,
        get_cnb_subareas_by_area_id,
        get_cnb_subarea_by_id
    ],
    system_prompt=SYSTEM_PROMPT_SPECIALIZED_QUERIES,
    middleware=[
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
