from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from auth.auth_handler import exchange_google_token_for_session, refresh_access_token_session


async def login_with_google(request):
    """
    Autentica al usuario validando el token de Google y emite tokens de sesión en cookies seguras.

    Args:
        request: Objeto de petición HTTP con el token de Google en el cuerpo JSON.

    Returns:
        JSONResponse: Respuesta JSON con la sesión creada y las cookies configuradas.
    """
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        raw_body = await request.json()
        body = raw_body if isinstance(raw_body, dict) else {}
        id_token_str = body.get("id_token")
        if not id_token_str or not str(id_token_str).strip():
            return JSONResponse({"detail": "El campo 'id_token' es obligatorio en el cuerpo de la petición."}, status_code=400)

        session = exchange_google_token_for_session(id_token_str)
        response = JSONResponse(session)

        response.set_cookie(
            key="access_token",
            value=session["access_token"],
            max_age=300,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/"
        )

        response.set_cookie(
            key="refresh_token",
            value=session["refresh_token"],
            max_age=604800,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/"
        )

        return response
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"detail": f"Error interno en la autenticación: {str(e)}"}, status_code=500)


async def refresh_token_endpoint(request):
    """
    Renueva el token de acceso utilizando la cookie de refresco de sesión.

    Args:
        request: Objeto de petición HTTP conteniendo la cookie 'refresh_token'.

    Returns:
        JSONResponse: Respuesta JSON con el nuevo token de acceso y la cookie actualizada.
    """
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        token = request.cookies.get("refresh_token")
        if not token:
            return JSONResponse(
                {"detail": "Acceso Denegado: Cookie 'refresh_token' no proporcionada."},
                status_code=401
            )

        new_session = refresh_access_token_session(token)
        response = JSONResponse(new_session)

        response.set_cookie(
            key="access_token",
            value=new_session["access_token"],
            max_age=300,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/"
        )

        return response
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=401)
    except Exception as e:
        return JSONResponse({"detail": f"Error interno en la renovación del token: {str(e)}"}, status_code=500)


async def logout(request):
    """
    Cierra la sesión activa eliminando las cookies de autenticación del usuario.

    Args:
        request: Objeto de petición HTTP.

    Returns:
        JSONResponse: Respuesta JSON confirmando el cierre de sesión.
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    response = JSONResponse({"status": "success", "message": "Sesión cerrada correctamente."})
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax", secure=True)
    response.delete_cookie(key="refresh_token", path="/", httponly=True, samesite="lax", secure=True)
    return response


routes = [
    Route("/auth/login", endpoint=login_with_google, methods=["POST", "OPTIONS"]),
    Route("/auth/refresh", endpoint=refresh_token_endpoint, methods=["POST", "OPTIONS"]),
    Route("/auth/logout", endpoint=logout, methods=["POST", "OPTIONS"]),
]

app = Starlette(debug=False, routes=routes)
