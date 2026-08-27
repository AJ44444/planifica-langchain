print(">>> [SERVER.PY] INICIANDO IMPORTACION Y DECLARACION DE SERVER.PY <<<", flush=True)

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from auth.auth_handler import exchange_google_token_for_session, refresh_access_token_session

print(">>> [SERVER.PY] IMPORTACIONES COMPLETADAS CORRECTAMENTE <<<", flush=True)


async def custom_health(request):
    """
    Endpoint GET de verificación de estado para confirmar que http.app se monta correctamente en LangGraph Server.
    """
    print(">>> [SERVER.PY] PETICION RECIBIDA EN GET /custom-health <<<", flush=True)
    return JSONResponse({
        "status": "ok",
        "message": "http.app montado correctamente en LangGraph Server",
        "routes": ["/auth/login", "/auth/refresh", "/auth/logout", "/custom-health"]
    }, status_code=200)


async def login_with_google(request):
    """
    1. Recibe el id_token de Google.
    2. Verifica la validez y firma con la biblioteca oficial de Google.
    3. Consulta o auto-registra al usuario en MongoDB.
    4. Emite un Access Token JWT propio (5 minutos) y un Refresh Token (7 días).
    5. Configura los tokens en cookies HTTP seguras (HttpOnly, SameSite=lax, Secure).
    """
    print(">>> [SERVER.PY] PETICION RECIBIDA EN POST /auth/login <<<", flush=True)
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
        
        # Configurar cookie para Access Token (5 min = 300 s)
        response.set_cookie(
            key="access_token",
            value=session["access_token"],
            max_age=300,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/"
        )
        
        # Configurar cookie para Refresh Token (7 días = 604800 s)
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
    Renueva el Access Token de 5 minutos extrayendo automáticamente el Refresh Token desde la cookie HTTP 'refresh_token'.
    Actualiza la cookie HttpOnly access_token con la nueva sesión.
    """
    print(">>> [SERVER.PY] PETICION RECIBIDA EN POST /auth/refresh <<<", flush=True)
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
        
        # Actualizar la cookie de Access Token (5 min = 300 s)
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
    Cierra la sesión del docente eliminando las cookies seguras access_token y refresh_token.
    """
    print(">>> [SERVER.PY] PETICION RECIBIDA EN POST /auth/logout <<<", flush=True)
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    response = JSONResponse({"status": "success", "message": "Sesión cerrada correctamente."})
    response.delete_cookie(key="access_token", path="/", httponly=True, samesite="lax", secure=True)
    response.delete_cookie(key="refresh_token", path="/", httponly=True, samesite="lax", secure=True)
    return response


routes = [
    Route("/custom-health", endpoint=custom_health, methods=["GET", "OPTIONS"]),
    Route("/custom-health/", endpoint=custom_health, methods=["GET", "OPTIONS"]),
    Route("/auth/login", endpoint=login_with_google, methods=["POST", "OPTIONS"]),
    Route("/auth/login/", endpoint=login_with_google, methods=["POST", "OPTIONS"]),
    Route("/auth/refresh", endpoint=refresh_token_endpoint, methods=["POST", "OPTIONS"]),
    Route("/auth/refresh/", endpoint=refresh_token_endpoint, methods=["POST", "OPTIONS"]),
    Route("/auth/logout", endpoint=logout, methods=["POST", "OPTIONS"]),
    Route("/auth/logout/", endpoint=logout, methods=["POST", "OPTIONS"]),
]

app = Starlette(debug=False, routes=routes)
print(">>> [SERVER.PY] INSTANCIA STARLETTE 'app' CREADA EXITOSAMENTE CON RUTAS <<<", flush=True)
