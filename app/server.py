from starlette.applications import Starlette
from starlette.routing import Route
from api.auth_handler import login_with_google, refresh_token_endpoint, logout
from api.lesson_plan_handler import get_paginated_lesson_plans_endpoint, get_lesson_plan_details_endpoint


routes = [
    Route("/auth/login", endpoint=login_with_google, methods=["POST", "OPTIONS"]),
    Route("/auth/refresh", endpoint=refresh_token_endpoint, methods=["POST", "OPTIONS"]),
    Route("/auth/logout", endpoint=logout, methods=["POST", "OPTIONS"]),
    Route("/api/lesson-plans", endpoint=get_paginated_lesson_plans_endpoint, methods=["GET", "OPTIONS"]),
    Route("/api/lesson-plans/{id_planificacion}", endpoint=get_lesson_plan_details_endpoint, methods=["GET", "OPTIONS"]),
]

app = Starlette(debug=False, routes=routes)
