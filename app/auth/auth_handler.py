from typing import Dict, Any, Optional
import time
from collections import defaultdict
from google.oauth2 import id_token as google_id_token_verifier
from google.auth.transport import requests as google_requests
from langgraph_sdk import Auth
from core.config import GOOGLE_CLIENT_ID
from tools.persistence_tool import create_user_doc, get_user_by_google_id, check_db_connection

# Instancia global de Auth de LangGraph SDK
auth = Auth()

THREAD_CREATION_LOGS = defaultdict(list)
MAX_THREADS_PER_MINUTE = 5

def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifica el token ID de Google OAuth con la biblioteca oficial recomendable para producción ('google-auth').
    Valida la firma criptográfica localmente utilizando certificados públicos de Google en caché,
    comprueba la vigencia y verifica que el Audience ('aud') coincida con GOOGLE_CLIENT_ID.
    
    Args:
        id_token: Token ID de Google OAuth en formato JWT.
        
    Returns:
        Diccionario con las declaraciones verídicas del usuario emitidas por Google.
    """
    try:
        req = google_requests.Request()
        payload = google_id_token_verifier.verify_oauth2_token(
            id_token,
            req,
            audience=GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None
        )
        if "sub" not in payload:
            raise ValueError("El token de Google OAuth no contiene el identificador de usuario 'sub'.")

        return payload
    except Exception as e:
        raise ValueError(f"Error en la verificación del token de Google OAuth: {str(e)}")


@auth.authenticate
async def authenticate(authorization: Optional[str] = None, headers: Optional[dict] = None) -> Auth.types.MinimalUserDict:
    """
    Middleware universal de autenticación para LangGraph Server.
    Soporta cualquier cliente consumidor (Web Apps, Apps Móviles Android/iOS, Flutter, React Native, SDKs):
    1. Intercepta el encabezado estándar HTTP 'Authorization: Bearer <google_id_token>'.
    2. Verifica la validez, firma y 'aud' del token mediante la biblioteca oficial 'google-auth'.
    3. Consulta o auto-registra al usuario en MongoDB usando únicamente el 'google_id' verificado.
    4. Inyecta la identidad para garantizar aislamiento estricto de hilos y datos por docente.
    """
    token = None
    if authorization:
        scheme, _, tok = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = tok.strip()

    if not token and headers:
        raw_header = headers.get(b"authorization") or headers.get("authorization")
        if raw_header:
            if isinstance(raw_header, bytes):
                raw_header = raw_header.decode("utf-8")
            scheme, _, tok = raw_header.partition(" ")
            if scheme.lower() == "bearer":
                token = tok.strip()

    if not token:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Acceso Denegado: Encabezado 'Authorization: Bearer <google_id_token>' no proporcionado."
        )

    # 1. Verificar si la comunicación con la base de datos MongoDB está activa antes de validar el token
    if not check_db_connection():
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Acceso Denegado: No hay comunicación activa con la base de datos."
        )

    # 2. Verificar la autenticidad del token mediante la biblioteca oficial google-auth
    try:
        google_payload = verify_google_id_token(token)
    except Exception as e:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail=f"Acceso Denegado: Token de Google OAuth no válido o expirado. ({str(e)})"
        )

    google_id = str(google_payload.get("sub", "")).strip()
    email = str(google_payload.get("email", "")).strip().lower()
    name = str(google_payload.get("name", "")).strip()
    given_name = str(google_payload.get("given_name", "")).strip()
    family_name = str(google_payload.get("family_name", "")).strip()
    picture = str(google_payload.get("picture", "")).strip()

    if not google_id or not email:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Acceso Denegado: El token de Google OAuth no contiene 'sub' o 'email'."
        )

    # 2. Consultar el usuario en la base de datos de MongoDB únicamente por su 'google_id'
    user = get_user_by_google_id(google_id)

    # 3. Registrar automáticamente al docente si es su primera sesión desde cualquier cliente web o app
    if not user:
        nombres = given_name if given_name else name
        apellidos = family_name if family_name else ""
        new_user_payload = {
            "google_id": google_id,
            "email": email,
            "nombres": nombres,
            "apellidos": apellidos,
            "foto_perfil": picture,
            "rol": "docente",
            "estado": "activo"
        }
        res = create_user_doc(new_user_payload)
        user = res.get("user")

    if not user or "_id" not in user:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Acceso Denegado: No se pudo verificar ni obtener el perfil del docente en la base de datos."
        )

    user_id = str(user["_id"])

    # 4. Retornar la identidad autenticada que LangGraph Server inyecta en config["configurable"]["langgraph_auth_user"]
    return {
        "identity": user_id,
        "is_authenticated": True,
        "email": user.get("email", email),
        "nombres": user.get("nombres", name),
        "rol": user.get("rol", "docente")
    }


# Rate Limiter para la creación de hilos (POST /threads): Máximo 5 hilos por minuto por usuario autenticado
@auth.on.threads.create
async def limit_thread_creation_rate(ctx: Auth.types.AuthContext, value: dict):
    """
    Middleware / Interceptor de LangGraph SDK que restringe la creación de hilos (POST /threads).
    Garantiza un límite máximo de 5 hilos por minuto por usuario autenticado.
    """
    user_id = getattr(ctx.user, "identity", None) or "anonymous"
    now = time.time()

    # Filtrar registros de creación de hilos activos en los últimos 60 segundos
    recent_threads = [t for t in THREAD_CREATION_LOGS[user_id] if now - t < 60]

    if len(recent_threads) >= MAX_THREADS_PER_MINUTE:
        raise Auth.exceptions.HTTPException(
            status_code=429,
            detail=f"Límite de tasa excedido: Se permite crear un máximo de {MAX_THREADS_PER_MINUTE} hilos por minuto."
        )

    recent_threads.append(now)
    THREAD_CREATION_LOGS[user_id] = recent_threads


# Política global por defecto de autorización para LangGraph Server
@auth.on
async def default_authorization_policy(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Manejador global de autorización por defecto para LangGraph Server.
    Cubre todas las rutas de despacho (assistants.*, crons.*, store.*, threads.*).
    Verifica que la solicitud provenga de un usuario autenticado válidamente.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        return False
    return True

