from langchain.agents import create_agent
from core.llm import llm
from tools.persistence_tool import (
    save_lesson_plan,
    get_planification_by_id,
    update_lesson_plan,
    delete_lesson_plan,
    get_cnb_careers_list,
    get_cnb_areas_by_careers,
    get_cnb_subareas_by_area_id,
    get_recent_lesson_plans,
    get_paginated_lesson_plans
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
        delete_lesson_plan,
        get_cnb_careers_list,
        get_cnb_areas_by_careers,
        get_cnb_subareas_by_area_id,
        get_recent_lesson_plans,
        get_paginated_lesson_plans
    ],
    system_prompt=SYSTEM_PROMPT_SCHOOL_LESSON_PLANS
)
