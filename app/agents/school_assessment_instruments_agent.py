from langchain.agents import create_agent
from core.llm import llm
from core.response_formats import InstrumentoEvaluacion
from tools.persistence_tool import (
    save_assessment_instrument,
    get_assessment_instrument_by_id,
    update_assessment_instrument,
    delete_assessment_instrument
)
from prompts.system_prompts import SYSTEM_PROMPT_SCHOOL_ASSESSMENT_INSTRUMENTS

agent = create_agent(
    model=llm,
    tools=[
        save_assessment_instrument,
        get_assessment_instrument_by_id,
        update_assessment_instrument,
        delete_assessment_instrument
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_ASSESSMENT_INSTRUMENTS,
    response_format=InstrumentoEvaluacion
)
