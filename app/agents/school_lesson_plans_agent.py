"""
Sub-agent responsible for managing teacher lesson plans.
"""
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.persistence_tool import (
    get_paginated_lesson_plans,
    save_lesson_plan,
    get_planification_by_id,
    update_lesson_plan,
    delete_lesson_plan
)
from tools.vector_tool import search_curriculum_vector_db
from middleware.security_middleware import SecurityGuardrailMiddleware
from core import load_prompt

agent = create_agent(
    model=llm,
    tools=[
        search_curriculum_vector_db,
        save_lesson_plan,
        get_paginated_lesson_plans,
        get_planification_by_id,
        update_lesson_plan,
        delete_lesson_plan
    ],
    system_prompt=load_prompt("school_lesson_plans.md"),
    name="planificador_clases_cnb",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
