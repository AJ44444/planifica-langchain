from starlette.requests import Request
from starlette.responses import JSONResponse
from auth.auth_handler import (
    exchange_google_token_for_session,
    get_or_refresh_session
)
from tools.persistence_tool import delete_session_by_session_id


async def login_with_google(request: Request) -> JSONResponse:
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        raw_body = await request.json()
        body = raw_body if isinstance(raw_body, dict) else {}
        id_token_str = body.get("id_token")
        if not id_token_str or not str(id_token_str).strip():
            return JSONResponse({"detail": "Field 'id_token' is required in request body."}, status_code=400)

        session = exchange_google_token_for_session(id_token_str)
        response = JSONResponse(session)

        response.set_cookie(
            key="session_id",
            value=session["session_id"],
            max_age=604800,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/"
        )
        response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax", secure=True)
        response.delete_cookie(key="refresh_token", path="/", httponly=True, samesite="lax", secure=True)

        return response
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"detail": f"Internal authentication error: {str(e)}"}, status_code=500)


async def logout(request: Request) -> JSONResponse:
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    session_id = request.cookies.get("session_id")
    if session_id:
        delete_session_by_session_id(session_id)

    response = JSONResponse({"status": "success", "message": "Logged out successfully."})
    response.delete_cookie(key="session_id", path="/", httponly=True, samesite="lax", secure=True)
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax", secure=True)
    response.delete_cookie(key="refresh_token", path="/", httponly=True, samesite="lax", secure=True)
    return response


async def verify_session(request: Request) -> JSONResponse:
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    session_id = request.cookies.get("session_id")
    if not session_id:
        return JSONResponse(
            {"detail": "Access Denied: 'session_id' cookie not provided."},
            status_code=401
        )

    try:
        payload = await get_or_refresh_session(session_id)
        return JSONResponse(
            {
                "status": "authenticated",
                "authenticated": True,
                "user": {
                    "id_usuario": str(payload.get("sub", "")),
                    "email": str(payload.get("email", "")),
                    "nombres": str(payload.get("nombres", "")),
                    "rol": str(payload.get("rol", "docente"))
                }
            },
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            {"detail": f"Access Denied: {str(e)}"},
            status_code=401
        )
