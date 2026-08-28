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

# Instancia global de Auth de LangGraph SDK
auth = Auth()

THREAD_CREATION_LOGS = defaultdict(list)
MAX_THREADS_PER_MINUTE = 5


def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verifica el token ID de Google OAuth con la biblioteca oficial recomendable para producción ('google-auth').
    Valida la firma criptográfica localmente utilizando certificados públicos de Google en caché,
    comprueba la vigencia y verifica que el Audience ('aud') coincida con GOOGLE_CLIENT_ID.
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
    Genera un Access Token JWT propio firmado con expiración máxima de 5 minutos (300 segundos).
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
    Genera un Refresh Token seguro con vigencia de 7 días y lo almacena en MongoDB.
    """
    token_str = secrets.token_hex(32)
    save_refresh_token(id_usuario=user_id, refresh_token=token_str, expires_in_days=expires_in_days)
    return token_str


def verify_project_access_token(token: str) -> Dict[str, Any]:
    """
    Verifica localmente la firma criptográfica y vigencia de nuestro JWT propio.
    """
    jwt_secret = get_env_variable("JWT_SECRET")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise ValueError("El token proporcionado no es un Access Token de sesión válido.")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("El Access Token ha expirado (duración máxima de 5 minutos). Requiere renovación.")
    except Exception as e:
        raise ValueError(f"Access Token no válido: {str(e)}")


def exchange_google_token_for_session(google_id_token_str: str) -> Dict[str, Any]:
    """
    Flujo de intercambio de autenticación:
    1. Recibe y verifica el ID token de Google.
    2. Consulta o auto-registra al docente en MongoDB.
    3. Genera un Access Token JWT propio con expiración de 5 minutos.
    4. Genera un Refresh Token con duración de 7 días.
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
    Renueva el Access Token de 5 minutos a partir de un Refresh Token activo de 7 días.
    """
    if not check_db_connection():
        raise ValueError("Acceso Denegado: No hay comunicación activa con la base de datos.")

    doc = get_refresh_token_doc(refresh_token_str)
    if not doc:
        raise ValueError("Refresh token no válido o expirado (duración máxima 7 días). Requiere iniciar sesión nuevamente.")

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
    Middleware universal de autenticación para LangGraph Server.
    Verifica estrictamente nuestro Access Token JWT propio (5 minutos) extraído de la cookie HTTP 'access_token':
    1. Permite acceso libre a las rutas públicas de autenticación (/auth/login, /auth/refresh, /auth/logout).
    2. Extrae únicamente de las cookies HTTP la clave 'access_token' para rutas de grafos.
    3. Verifica la firma y expiración de nuestro JWT propio (< 1ms).
    4. Inyecta la identidad para garantizar aislamiento estricto de hilos y datos por docente.
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

    # Validar que el token sea nuestro Access Token JWT propio (duración máxima 5 min)
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


# Interceptor de autorización de hilos (threads): Aislamiento estricto por docente
@auth.on.threads
async def authorize_threads(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Garantiza aislamiento estricto entre docentes (Usuario A no puede acceder a hilos ni ejecuciones del Usuario B):
    1. Asigna la propiedad del hilo en los metadatos ('owner': ctx.user.identity).
    2. Retorna un filtro {'owner': ctx.user.identity} para restringir lectura, búsqueda y ejecución exclusivamente al propietario.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


# Rate Limiter y asignación de propiedad para creación de hilos (POST /threads)
@auth.on.threads.create
async def limit_thread_creation_rate(ctx: Auth.types.AuthContext, value: dict):
    """
    Middleware / Interceptor de LangGraph SDK que restringe la creación de hilos (POST /threads):
    1. Garantiza un límite máximo de 5 hilos por minuto por usuario autenticado.
    2. Etiqueta la propiedad del hilo con el ID único del docente.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
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

    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


# Interceptor de autorización para la tienda de memoria persistente (BaseStore)
@auth.on.store
async def authorize_store(ctx: Auth.types.AuthContext, value: dict):
    """
    Aísla los elementos almacenados en la tienda (BaseStore) por docente:
    Reescribe el namespace anteponiendo la identidad del usuario ('user_id', ...) para evitar lecturas/escrituras cruzadas.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Acceso Denegado: Usuario no autenticado.")

    user_id = ctx.user.identity
    namespace = value.get("namespace", ())
    if not namespace or namespace[0] != user_id:
        value["namespace"] = (user_id,) + tuple(namespace)


# Política global por defecto de autorización para LangGraph Server
@auth.on
async def default_authorization_policy(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Manejador global de autorización por defecto para LangGraph Server.
    Cubre todas las rutas no manejadas específicamente (assistants.*, crons.*).
    Verifica que la solicitud provenga de un usuario autenticado válidamente.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        return False
    return True

