"""
Módulo de herramientas del sistema Planifica (Parseo de PDF, Búsqueda Vectorial, Búsqueda Web SERPER y Persistencia MongoDB).
"""

from .parser_tool import (
    convert_pdf_to_markdown,
    extract_career_name,
    extract_curricular_structure_table,
    parse_curricular_areas,
)
from .vector_tool import search_curriculum_vector_db, generate_subarea_vector_embeddings, vector_search_cnb
from .web_search_tool import serper_web_search
from .persistence_tool import (
    save_lesson_plan,
    get_planification_by_id,
    update_lesson_plan,
    delete_lesson_plan,
    save_assessment_instrument,
    get_assessment_instrument_by_id,
    update_assessment_instrument,
    delete_assessment_instrument,
    save_multimodal_resource,
    get_multimodal_resource_by_id,
    update_multimodal_resource,
    delete_multimodal_resource,
    get_top_frequent_courses,
    get_recent_lesson_plans,
    get_latest_plan_instruments_and_resources,
    get_paginated_lesson_plans,
    get_full_lesson_plan_details,
    get_cnb_careers_list,
    get_cnb_areas_by_career,
    get_cnb_subareas_by_area_id,
    extract_user_id_from_config,
)

__all__ = [
    "convert_pdf_to_markdown",
    "extract_career_name",
    "extract_curricular_structure_table",
    "parse_curricular_areas",
    "search_curriculum_vector_db",
    "generate_subarea_vector_embeddings",
    "vector_search_cnb",
    "serper_web_search",
    "save_lesson_plan",
    "get_planification_by_id",
    "update_lesson_plan",
    "delete_lesson_plan",
    "save_assessment_instrument",
    "get_assessment_instrument_by_id",
    "update_assessment_instrument",
    "delete_assessment_instrument",
    "save_multimodal_resource",
    "get_multimodal_resource_by_id",
    "update_multimodal_resource",
    "delete_multimodal_resource",
    "get_top_frequent_courses",
    "get_recent_lesson_plans",
    "get_latest_plan_instruments_and_resources",
    "get_paginated_lesson_plans",
    "get_full_lesson_plan_details",
    "get_cnb_careers_list",
    "get_cnb_areas_by_career",
    "get_cnb_subareas_by_area_id",
    "extract_user_id_from_config",
]
