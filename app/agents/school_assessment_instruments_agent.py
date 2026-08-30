from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.persistence_tool import (
    save_assessment_instrument,
    get_assessment_instrument_by_id,
    update_assessment_instrument,
    delete_assessment_instrument,
    get_paginated_lesson_plans,
    get_full_lesson_plan_details
)
from middleware.security_middleware import SecurityGuardrailMiddleware
from prompts.system_prompts import SYSTEM_PROMPT_SCHOOL_ASSESSMENT_INSTRUMENTS

agent = create_agent(
    model=llm,
    tools=[
        save_assessment_instrument,
        get_assessment_instrument_by_id,
        update_assessment_instrument,
        delete_assessment_instrument,
        get_paginated_lesson_plans,
        get_full_lesson_plan_details
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_ASSESSMENT_INSTRUMENTS,
    name="instrumentos_evaluacion_cnb",
    middleware=[
        SecurityGuardrailMiddleware(),
        SummarizationMiddleware(
            model=llm,
            trigger=("messages", 30),
            keep=("messages", 15)
        )
    ]
)
