import jwt
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import time
from collections import defaultdict
from google.oauth2 import id_token as google_id_token_verifier
from google.auth.transport import requests as google_requests
from langgraph_sdk import Auth
from core.config import get_env_variable
from tools.persistence_tool import (
    create_user_doc,
    get_user_by_google_id,
    get_user_profile_doc,
    check_db_connection,
    save_refresh_token,
    get_refresh_token_doc,
)

auth = Auth()

THREAD_CREATION_LOGS = defaultdict(list)
MAX_THREADS_PER_MINUTE = 5


def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifica la autenticidad y vigencia de un token ID de Google OAuth.

    Args:
        id_token (str): Cadena de token ID emitida por Google.

    Returns:
        Dict[str, Any]: Carga útil (payload) del token validado con los datos del usuario.
    """
    try:
        client_id = get_env_variable("GOOGLE_CLIENT_ID")
        req = google_requests.Request()
        payload = google_id_token_verifier.verify_oauth2_token(
            id_token,
            req,
            audience=client_id
        )
        if "sub" not in payload:
            raise ValueError("El token de Google OAuth no contiene el identificador de usuario 'sub'.")

        return payload
    except Exception as e:
        raise ValueError(f"Error en la verificación del token de Google OAuth: {str(e)}")


def create_access_token(user_id: str, email: str, nombres: str = "", rol: str = "docente", expires_in_seconds: int = 300) -> str:
    """
    Genera un token de acceso JWT firmado para el usuario.

    Args:
        user_id (str): Identificador único del usuario.
        email (str): Correo electrónico del usuario.
        nombres (str, opcional): Nombres del usuario.
        rol (str, opcional): Rol asignado. Por defecto 'docente'.
        expires_in_seconds (int, opcional): Tiempo de expiración en segundos. Por defecto 300.

    Returns:
        str: Token de acceso JWT codificado.
    """
    jwt_secret = get_env_variable("JWT_SECRET")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id).strip(),
        "email": str(email).strip(),
        "nombres": str(nombres).strip(),
        "rol": str(rol).strip(),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp())
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def create_refresh_token(user_id: str, expires_in_days: int = 7) -> str:
    """
    Genera y almacena un token de refresco para el usuario.

    Args:
        user_id (str): Identificador único del usuario.
        expires_in_days (int, opcional): Días de validez del token. Por defecto 7.

    Returns:
        str: Cadena única del token de refresco generado.
    """
    token_str = secrets.token_hex(32)
    save_refresh_token(id_usuario=user_id, refresh_token=token_str, expires_in_days=expires_in_days)
    return token_str


def verify_project_access_token(token: str) -> Dict[str, Any]:
    """
    Verifica la firma y vigencia de un token de acceso JWT.

    Args:
        token (str): Token de acceso JWT a validar.

    Returns:
        Dict[str, Any]: Carga útil del token validado.
    """
    jwt_secret = get_env_variable("JWT_SECRET")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise ValueError("El token proporcionado no es un Access Token de sesión válido.")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("El Access Token ha expirado. Requiere renovación.")
    except Exception as e:
        raise ValueError(f"Access Token no válido: {str(e)}")


def exchange_google_token_for_session(google_id_token_str: str) -> Dict[str, Any]:
    """
    Intercambia un token de Google OAuth por una sesión de usuario con sus respectivos tokens de acceso y refresco.

    Args:
        google_id_token_str (str): Token ID de Google OAuth.

    Returns:
        Dict[str, Any]: Diccionario con los tokens emitidos y datos del usuario.
    """
    if not check_db_connection():
        raise ValueError("Acceso Denegado: No hay comunicación activa con la base de datos.")

    google_payload = verify_google_id_token(google_id_token_str)
    google_id = str(google_payload.get("sub", "")).strip()
    email = str(google_payload.get("email", "")).strip().lower()
    name = str(google_payload.get("name", "")).strip()
    given_name = str(google_payload.get("given_name", "")).strip()
    family_name = str(google_payload.get("family_name", "")).strip()
    picture = str(google_payload.get("picture", "")).strip()

    if not google_id or not email:
        raise ValueError("Acceso Denegado: El token de Google OAuth no contiene 'sub' o 'email'.")

    user = get_user_by_google_id(google_id)
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
        raise ValueError("Acceso Denegado: No se pudo verificar ni obtener el perfil del docente en la base de datos.")

    user_id = str(user["_id"])
    access_token = create_access_token(
        user_id=user_id,
        email=user.get("email", email),
        nombres=user.get("nombres", name),
        rol=user.get("rol", "docente"),
        expires_in_seconds=300
    )
    refresh_token = create_refresh_token(user_id=user_id, expires_in_days=7)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 300,
        "token_type": "Bearer",
        "user": {
            "id_usuario": user_id,
            "email": user.get("email", email),
            "nombres": user.get("nombres", name),
            "rol": user.get("rol", "docente")
        }
    }


def refresh_access_token_session(refresh_token_str: str) -> Dict[str, Any]:
    """
    Renueva la sesión emitiendo un nuevo token de acceso a partir de un token de refresco válido.

    Args:
        refresh_token_str (str): Token de refresco de sesión activa.

    Returns:
        Dict[str, Any]: Diccionario con el nuevo token de acceso.
    """
    if not check_db_connection():
        raise ValueError("Acceso Denegado: No hay comunicación activa con la base de datos.")

    doc = get_refresh_token_doc(refresh_token_str)
    if not doc:
        raise ValueError("Refresh token no válido o expirado. Requiere iniciar sesión nuevamente.")

    id_usuario = str(doc.get("id_usuario") or doc.get("user_id", "")).strip()
    user = get_user_profile_doc(id_usuario)
    if not user:
        raise ValueError("Acceso Denegado: El usuario asociado al refresh token no fue encontrado.")

    user_id = str(user["_id"])
    new_access_token = create_access_token(
        user_id=user_id,
        email=user.get("email", ""),
        nombres=user.get("nombres", ""),
        rol=user.get("rol", "docente"),
        expires_in_seconds=300
    )

    return {
        "access_token": new_access_token,
        "expires_in": 300,
        "token_type": "Bearer"
    }


@auth.authenticate
async def authenticate(
    authorization: Optional[str] = None,
    headers: Optional[dict] = None,
    path: Optional[str] = None
) -> Auth.types.MinimalUserDict:
    """
    Autentica las solicitudes extrayendo y validando la cookie de sesión.

    Args:
        authorization (opcional): Encabezado de autorización.
        headers (opcional): Diccionario de encabezados HTTP.
        path (opcional): Ruta de la petición solicitada.

    Returns:
        Auth.types.MinimalUserDict: Diccionario con la identidad y estado de autenticación del usuario.
    """
    path_str = str(path.decode("utf-8") if isinstance(path, bytes) else (path or "")).strip()
    path_clean = path_str if path_str.startswith("/") else f"/{path_str}"
    path_normalized = path_clean.rstrip("/") if len(path_clean) > 1 else path_clean
    if path_normalized in {"/auth/login", "/auth/refresh", "/auth/logout"}:
        return {
            "identity": "anonymous",
            "is_authenticated": False
        }

    token = None
    if headers:
        cookie_header = headers.get(b"cookie") or headers.get("cookie")
        if cookie_header:
            if isinstance(cookie_header, bytes):
                cookie_header = cookie_header.decode("utf-8")
            from http.cookies import SimpleCookie
            cookie_parser = SimpleCookie()
            cookie_parser.load(cookie_header)
            if "access_token" in cookie_parser:
                token = cookie_parser["access_token"].value.strip()

    if not token:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Acceso Denegado: Cookie 'access_token' no proporcionada."
        )

    try:
        jwt_payload = verify_project_access_token(token)
        return {
            "identity": str(jwt_payload["sub"]),
            "is_authenticated": True,
            "email": str(jwt_payload.get("email", "")),
            "nombres": str(jwt_payload.get("nombres", "")),
            "rol": str(jwt_payload.get("rol", "docente"))
        }
    except Exception as jwt_err:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail=f"Acceso Denegado: {str(jwt_err)}"
        )


@auth.on.threads
async def authorize_threads(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Valida los permisos de acceso a hilos de conversación filtrando por el propietario.

    Args:
        ctx (Auth.types.AuthContext): Contexto de autenticación del usuario.
        value (dict, opcional): Datos del hilo de conversación.

    Returns:
        dict: Filtro de propiedad con el identificador del usuario.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


@auth.on.threads.create
async def limit_thread_creation_rate(ctx: Auth.types.AuthContext, value: dict):
    """
    Aplica el control de tasa en la creación de hilos asignando la propiedad del hilo al usuario.

    Args:
        ctx (Auth.types.AuthContext): Contexto de autenticación del usuario.
        value (dict): Datos del nuevo hilo a crear.

    Returns:
        dict: Filtro de propiedad asignado al hilo.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
    now = time.time()

    recent_threads = [t for t in THREAD_CREATION_LOGS[user_id] if now - t < 60]

    if len(recent_threads) >= MAX_THREADS_PER_MINUTE:
        raise Auth.exceptions.HTTPException(
            status_code=429,
            detail=f"Límite de tasa excedido: Se permite crear un máximo de {MAX_THREADS_PER_MINUTE} hilos por minuto."
        )

    recent_threads.append(now)
    THREAD_CREATION_LOGS[user_id] = recent_threads

    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


@auth.on.store
async def authorize_store(ctx: Auth.types.AuthContext, value: dict):
    """
    Restringe el acceso al almacén persistente delimitando el espacio de nombres por usuario.

    Args:
        ctx (Auth.types.AuthContext): Contexto de autenticación.
        value (dict): Datos y espacio de nombres del elemento en el almacén.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
    namespace = value.get("namespace", ())
    if not namespace or namespace[0] != user_id:
        value["namespace"] = (user_id,) + tuple(namespace)


@auth.on
async def default_authorization_policy(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Evalúa la política global de autorización para solicitudes entrantes.

    Args:
        ctx (Auth.types.AuthContext): Contexto de autenticación.
        value (dict, opcional): Datos adicionales de la solicitud.

    Returns:
        bool: True si la solicitud está autorizada, False en caso contrario.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        return False
    return True
