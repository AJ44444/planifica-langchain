"""
Módulo de agentes y subagentes del Sistema Multiagente Planifica.
"""

from .main_agent import main_agent
from .process_pdf_agent import agent as process_pdf_agent
from .school_lesson_plans_agent import agent as school_lesson_plans_agent
from .school_assessment_instruments_agent import agent as school_assessment_instruments_agent
from .school_multimodal_resources_agent import agent as school_multimodal_resources_agent
from .specialized_queries_agent import agent as specialized_queries_agent

__all__ = [
    "main_agent",
    "process_pdf_agent",
    "school_lesson_plans_agent",
    "school_assessment_instruments_agent",
    "school_multimodal_resources_agent",
    "specialized_queries_agent",
]
