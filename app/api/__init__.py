"""
Módulo API con handlers y endpoints de la aplicación Planifica.
"""
from .lesson_plan_handler import (
    get_paginated_lesson_plans_endpoint,
    get_lesson_plan_details_endpoint,
)

__all__ = [
    "get_paginated_lesson_plans_endpoint",
    "get_lesson_plan_details_endpoint",
]
