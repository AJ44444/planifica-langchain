import jwt
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
import time
from collections import defaultdict
from google.oauth2 import id_token as google_id_token_verifier
from google.auth.transport import requests as google_requests
from langgraph_sdk import Auth
from core.config import get_env_variable
from core import (
    GoogleIdTokenPayload,
    JWTAccessTokenPayload,
    SessionResponseDict,
)
from tools.persistence_tool import (
    create_user_doc,
    get_user_profile_doc,
    check_db_connection,
    save_session_doc,
    get_session_by_session_id,
    update_session_tokens,
    delete_session_by_session_id,
)

auth = Auth()

THREAD_CREATION_LOGS = defaultdict(list)
MAX_THREADS_PER_MINUTE = 5

_SESSION_LOCKS: Dict[str, asyncio.Lock] = {}
_LOCKS_GUARD = asyncio.Lock()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    async with _LOCKS_GUARD:
        if session_id not in _SESSION_LOCKS:
            _SESSION_LOCKS[session_id] = asyncio.Lock()
        return _SESSION_LOCKS[session_id]


def verify_google_id_token(id_token: str) -> GoogleIdTokenPayload:
    try:
        client_id = get_env_variable("GOOGLE_CLIENT_ID")
        req = google_requests.Request()
        payload: GoogleIdTokenPayload = google_id_token_verifier.verify_oauth2_token(
            id_token,
            req,
            audience=client_id
        )
        if "sub" not in payload:
            raise ValueError("Google OAuth token does not contain user identifier 'sub'.")
        if "email" not in payload:
            raise ValueError("Google OAuth token does not contain user email.")

        return payload
    except Exception as e:
        raise ValueError(f"Error verifying Google OAuth token: {str(e)}")


def create_access_token(user_id: str, email: str, nombres: str = "", rol: str = "docente", expires_in_seconds: int = 300) -> str:
    jwt_secret = get_env_variable("JWT_SECRET")
    now = datetime.now(timezone.utc)
    payload: JWTAccessTokenPayload = {
        "sub": str(user_id).strip(),
        "email": str(email).strip(),
        "nombres": str(nombres).strip(),
        "rol": str(rol).strip(),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp())
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def verify_project_access_token(token: str) -> JWTAccessTokenPayload:
    jwt_secret = get_env_variable("JWT_SECRET")
    try:
        payload: JWTAccessTokenPayload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise ValueError("The provided token is not a valid session Access Token.")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Access Token has expired. Renewal required.")
    except Exception as e:
        raise ValueError(f"Invalid Access Token: {str(e)}")


def exchange_google_token_for_session(google_id_token_str: str) -> SessionResponseDict:
    if not check_db_connection():
        raise ValueError("Access Denied: Database connection is not active.")

    google_payload = verify_google_id_token(google_id_token_str)

    google_id = str(google_payload.get("sub", "")).strip()
    email = str(google_payload.get("email", "")).strip().lower()
    name = str(google_payload.get("name", "")).strip()
    given_name = str(google_payload.get("given_name", "")).strip()
    family_name = str(google_payload.get("family_name", "")).strip()
    picture = str(google_payload.get("picture", "")).strip()

    nombres = given_name if given_name else name
    apellidos = family_name if family_name else ""

    user_payload = {
        "google_id": google_id,
        "email": email,
        "nombres": nombres,
        "apellidos": apellidos,
        "foto_perfil": picture,
        "rol": "docente",
        "estado": "activo"
    }

    res = create_user_doc(user_payload)
    user = res.get("user")

    if not user or "_id" not in user:
        raise ValueError("Access Denied: Could not verify or retrieve teacher profile from database.")

    user_id = str(user["_id"])
    session_id = secrets.token_hex(32)
    access_token = create_access_token(
        user_id=user_id,
        email=user.get("email", email),
        nombres=user.get("nombres", name),
        rol=user.get("rol", "docente"),
        expires_in_seconds=300
    )
    refresh_token = secrets.token_hex(32)

    save_session_doc(
        id_usuario=user_id,
        session_id=session_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_days=7
    )

    return {
        "session_id": session_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 604800,
        "token_type": "Bearer",
        "user": {
            "id_usuario": user_id,
            "email": user.get("email", email),
            "nombres": user.get("nombres", name),
            "rol": user.get("rol", "docente")
        }
    }


async def get_or_refresh_session(session_id: str) -> JWTAccessTokenPayload:
    sid = str(session_id).strip()
    if not sid:
        raise ValueError("Access Denied: 'session_id' cookie not provided.")

    lock = await _get_session_lock(sid)
    async with lock:
        session_doc = get_session_by_session_id(sid)
        if not session_doc:
            raise ValueError("Access Denied: Invalid or expired session. Please log in again.")

        access_token = str(session_doc.get("access_token", "")).strip()

        if access_token:
            try:
                jwt_payload = verify_project_access_token(access_token)
                return jwt_payload
            except ValueError:
                pass

        user_id = str(session_doc.get("id_usuario", "")).strip()
        user = get_user_profile_doc(user_id)
        if not user:
            delete_session_by_session_id(sid)
            raise ValueError("Access Denied: User associated with session was not found.")

        new_access_token = create_access_token(
            user_id=str(user["_id"]),
            email=user.get("email", ""),
            nombres=user.get("nombres", ""),
            rol=user.get("rol", "docente"),
            expires_in_seconds=300
        )
        new_refresh_token = secrets.token_hex(32)

        updated = update_session_tokens(
            session_id=sid,
            new_access_token=new_access_token,
            new_refresh_token=new_refresh_token
        )
        if not updated:
            raise ValueError("Access Denied: Failed to renew session tokens.")

        return verify_project_access_token(new_access_token)


@auth.authenticate
async def authenticate(
    authorization: Optional[str] = None,
    headers: Optional[dict] = None,
    path: Optional[str] = None
) -> Auth.types.MinimalUserDict:
    path_str = path.decode("utf-8") if isinstance(path, bytes) else (path or "")
    if path_str.rstrip("/") in {"/auth/login", "/auth/logout", "/auth/verify"}:
        return {"identity": "anonymous", "is_authenticated": False}

    session_id = None
    if headers:
        raw_cookie = headers.get(b"cookie") or headers.get("cookie") or ""
        cookie_str = raw_cookie.decode("utf-8") if isinstance(raw_cookie, bytes) else raw_cookie
        if "session_id=" in cookie_str:
            from http.cookies import SimpleCookie
            cookie_parser = SimpleCookie()
            cookie_parser.load(cookie_str)
            if "session_id" in cookie_parser:
                session_id = cookie_parser["session_id"].value.strip()

    if not session_id:
        raise Auth.exceptions.HTTPException(
            status_code=401,
            detail="Access Denied: 'session_id' cookie not provided."
        )

    try:
        jwt_payload = await get_or_refresh_session(session_id)
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
            detail=f"Access Denied: {str(jwt_err)}"
        )


@auth.on.threads
async def authorize_threads(ctx: Auth.types.AuthContext, value: Optional[dict] = None) -> Dict[str, str]:
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Access Denied: User not authenticated.")

    user_id = ctx.user.identity
    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


@auth.on.threads.create
async def limit_thread_creation_rate(ctx: Auth.types.AuthContext, value: dict) -> Dict[str, str]:
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Access Denied: User not authenticated.")

    user_id = ctx.user.identity
    now = time.time()

    recent_threads = [t for t in THREAD_CREATION_LOGS[user_id] if now - t < 60]

    if len(recent_threads) >= MAX_THREADS_PER_MINUTE:
        raise Auth.exceptions.HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: Maximum of {MAX_THREADS_PER_MINUTE} threads per minute allowed."
        )

    recent_threads.append(now)
    THREAD_CREATION_LOGS[user_id] = recent_threads

    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


@auth.on.store
async def authorize_store(ctx: Auth.types.AuthContext, value: dict) -> None:
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Access Denied: User not authenticated.")

    user_id = ctx.user.identity
    namespace = value.get("namespace", ())
    if not namespace or namespace[0] != user_id:
        value["namespace"] = (user_id,) + tuple(namespace)


@auth.on
async def default_authorization_policy(ctx: Auth.types.AuthContext, value: Optional[dict] = None) -> bool:
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        return False
    return True
