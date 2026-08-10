from langchain.agents import create_agent
from core.llm import llm
from tools.persistence_tool import (
    save_lesson_plan,
    get_planification_by_id,
    update_lesson_plan,
    delete_lesson_plan
)
from tools.vector_tool import search_curriculum_vector_db
from prompts.system_prompts import SYSTEM_PROMPT_SCHOOL_LESSON_PLANS

agent = create_agent(
    model=llm,
    tools=[
        search_curriculum_vector_db,
        save_lesson_plan,
        get_planification_by_id,
        update_lesson_plan,
        delete_lesson_plan
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_LESSON_PLANS
)
