from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from core.llm import llm
from tools.persistence_tool import (
    save_assessment_instrument,
    get_assessment_instrument_by_id,
    update_assessment_instrument,
    delete_assessment_instrument,
    get_learning_activity_by_id
)
from middleware.security_middleware import SecurityGuardrailMiddleware
from core import load_prompt

agent = create_agent(
    model=llm,
    tools=[
        get_learning_activity_by_id,
        save_assessment_instrument,
        get_assessment_instrument_by_id,
        update_assessment_instrument,
        delete_assessment_instrument
    ],
    system_prompt=load_prompt("school_assessment_instruments.md"),
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
