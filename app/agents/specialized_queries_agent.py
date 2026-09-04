from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.persistence_tool import (
    get_top_frequent_courses,
    get_paginated_lesson_plans,
    get_lesson_plan_details,
    get_cnb_careers_list,
    get_cnb_areas_by_career,
    get_cnb_subareas_by_area_id,
    get_cnb_area_by_id,
    get_cnb_subarea_by_id
)
from middleware.security_middleware import SecurityGuardrailMiddleware
from core import load_prompt

agent = create_agent(
    model=llm,
    tools=[
        get_top_frequent_courses,
        get_paginated_lesson_plans,
        get_lesson_plan_details,
        get_cnb_careers_list,
        get_cnb_areas_by_career,
        get_cnb_subareas_by_area_id,
        get_cnb_area_by_id,
        get_cnb_subarea_by_id
    ],
    system_prompt=load_prompt("specialized_queries.md"),
    name="consultas_especializadas_cnb",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
