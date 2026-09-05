"""
Módulo API con handlers y endpoints de la aplicación Planifica.
"""
from .lesson_plan_handler import (
    get_paginated_lesson_plans_endpoint,
    get_lesson_plan_details_endpoint,
)
from .auth_handler import (
    login_with_google,
    refresh_token_endpoint,
    logout,
)

__all__ = [
    "get_paginated_lesson_plans_endpoint",
    "get_lesson_plan_details_endpoint",
    "login_with_google",
    "refresh_token_endpoint",
    "logout",
]
