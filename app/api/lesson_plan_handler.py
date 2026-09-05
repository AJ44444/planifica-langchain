import json
from starlette.requests import Request
from starlette.responses import JSONResponse
from tools.persistence_tool import get_paginated_lesson_plans, get_lesson_plan_details
from auth.auth_handler import verify_project_access_token


def extract_user_id_from_request(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        return ""
    try:
        payload = verify_project_access_token(token)
        return str(payload.get("sub", "")).strip()
    except Exception:
        return ""


async def get_paginated_lesson_plans_endpoint(request: Request) -> JSONResponse:
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        user_id = extract_user_id_from_request(request)
        if not user_id:
            return JSONResponse(
                {"detail": "Access Denied: Invalid or missing access token."},
                status_code=401
            )

        try:
            page = int(request.query_params.get("page", 1))
        except (ValueError, TypeError):
            page = 1

        try:
            limit = int(request.query_params.get("limit", 10))
        except (ValueError, TypeError):
            limit = 10

        res_str = get_paginated_lesson_plans.func(
            id_usuario=user_id,
            page=page,
            limit=limit
        )

        res_data = json.loads(res_str)
        if res_data.get("status") == "error":
            return JSONResponse({"detail": res_data.get("message", "Error querying history.")}, status_code=400)

        return JSONResponse(res_data, status_code=200)
    except Exception as e:
        return JSONResponse({"detail": f"Internal server error: {str(e)}"}, status_code=500)


async def get_lesson_plan_details_endpoint(request: Request) -> JSONResponse:
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        user_id = extract_user_id_from_request(request)
        if not user_id:
            return JSONResponse(
                {"detail": "Access Denied: Invalid or missing access token."},
                status_code=401
            )

        id_planificacion = request.path_params.get("id_planificacion", "").strip()
        if not id_planificacion:
            return JSONResponse({"detail": "Parameter 'id_planificacion' is required."}, status_code=400)

        res_str = get_lesson_plan_details.func(
            id_planificacion=id_planificacion,
            id_usuario=user_id
        )

        res_data = json.loads(res_str)
        if res_data.get("status") == "error":
            return JSONResponse({"detail": res_data.get("message", "Lesson plan not found.")}, status_code=404)

        return JSONResponse(res_data, status_code=200)
    except Exception as e:
        return JSONResponse({"detail": f"Internal server error: {str(e)}"}, status_code=500)
