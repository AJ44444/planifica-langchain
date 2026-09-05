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
    Verifies the authenticity and validity of a Google OAuth ID token.

    Args:
        id_token (str): Google OAuth ID token string.

    Returns:
        Dict[str, Any]: Verified token payload containing user details.
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
            raise ValueError("Google OAuth token does not contain user identifier 'sub'.")

        return payload
    except Exception as e:
        raise ValueError(f"Error verifying Google OAuth token: {str(e)}")


def create_access_token(user_id: str, email: str, nombres: str = "", rol: str = "docente", expires_in_seconds: int = 300) -> str:
    """
    Generates a signed JWT access token for the user.

    Args:
        user_id (str): Unique user identifier.
        email (str): User email address.
        nombres (str, optional): User first names.
        rol (str, optional): Assigned role. Defaults to 'docente'.
        expires_in_seconds (int, optional): Expiration time in seconds. Defaults to 300.

    Returns:
        str: Encoded JWT access token string.
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
    Generates and persists a refresh token for the user.

    Args:
        user_id (str): Unique user identifier.
        expires_in_days (int, optional): Token validity in days. Defaults to 7.

    Returns:
        str: Unique generated refresh token string.
    """
    token_str = secrets.token_hex(32)
    save_refresh_token(id_usuario=user_id, refresh_token=token_str, expires_in_days=expires_in_days)
    return token_str


def verify_project_access_token(token: str) -> Dict[str, Any]:
    """
    Verifies the signature and expiration of a JWT access token.

    Args:
        token (str): JWT access token to validate.

    Returns:
        Dict[str, Any]: Payload of the verified token.
    """
    jwt_secret = get_env_variable("JWT_SECRET")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise ValueError("The provided token is not a valid session Access Token.")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Access Token has expired. Renewal required.")
    except Exception as e:
        raise ValueError(f"Invalid Access Token: {str(e)}")


def exchange_google_token_for_session(google_id_token_str: str) -> Dict[str, Any]:
    """
    Exchanges a Google OAuth token for a user session with access and refresh tokens.

    Args:
        google_id_token_str (str): Google OAuth ID token.

    Returns:
        Dict[str, Any]: Dictionary containing issued tokens and user data.
    """
    if not check_db_connection():
        raise ValueError("Access Denied: Database connection is not active.")

    google_payload = verify_google_id_token(google_id_token_str)
    google_id = str(google_payload.get("sub", "")).strip()
    email = str(google_payload.get("email", "")).strip().lower()
    name = str(google_payload.get("name", "")).strip()
    given_name = str(google_payload.get("given_name", "")).strip()
    family_name = str(google_payload.get("family_name", "")).strip()
    picture = str(google_payload.get("picture", "")).strip()

    if not google_id or not email:
        raise ValueError("Access Denied: Google OAuth token missing 'sub' or 'email'.")

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
        raise ValueError("Access Denied: Could not verify or retrieve teacher profile from database.")

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
    Renews the session issuing a new access token from a valid refresh token.

    Args:
        refresh_token_str (str): Active session refresh token.

    Returns:
        Dict[str, Any]: Dictionary containing the new access token.
    """
    if not check_db_connection():
        raise ValueError("Access Denied: Database connection is not active.")

    doc = get_refresh_token_doc(refresh_token_str)
    if not doc:
        raise ValueError("Invalid or expired refresh token. Please sign in again.")

    id_usuario = str(doc.get("id_usuario") or doc.get("user_id", "")).strip()
    user = get_user_profile_doc(id_usuario)
    if not user:
        raise ValueError("Access Denied: User associated with refresh token was not found.")

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
    Authenticates requests by extracting and validating the session cookie.

    Args:
        authorization (optional): Authorization header.
        headers (optional): HTTP headers dictionary.
        path (optional): Requested path.

    Returns:
        Auth.types.MinimalUserDict: Dictionary containing user identity and authentication status.
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
            detail="Access Denied: 'access_token' cookie not provided."
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
            detail=f"Access Denied: {str(jwt_err)}"
        )


@auth.on.threads
async def authorize_threads(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Validates thread access permissions by filtering by owner.

    Args:
        ctx (Auth.types.AuthContext): User authentication context.
        value (dict, optional): Conversation thread data.

    Returns:
        dict: Ownership filter containing user ID.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Access Denied: User not authenticated.")

    user_id = ctx.user.identity
    if isinstance(value, dict):
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = user_id

    return {"owner": user_id}


@auth.on.threads.create
async def limit_thread_creation_rate(ctx: Auth.types.AuthContext, value: dict):
    """
    Applies thread creation rate limiting and assigns thread ownership to the user.

    Args:
        ctx (Auth.types.AuthContext): User authentication context.
        value (dict): New thread data.

    Returns:
        dict: Ownership filter assigned to thread.
    """
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
async def authorize_store(ctx: Auth.types.AuthContext, value: dict):
    """
    Restricts persistent store access by namespacing by user ID.

    Args:
        ctx (Auth.types.AuthContext): Authentication context.
        value (dict): Store item data and namespace.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Access Denied: User not authenticated.")

    user_id = ctx.user.identity
    namespace = value.get("namespace", ())
    if not namespace or namespace[0] != user_id:
        value["namespace"] = (user_id,) + tuple(namespace)


@auth.on
async def default_authorization_policy(ctx: Auth.types.AuthContext, value: dict = None):
    """
    Evaluates global authorization policy for incoming requests.

    Args:
        ctx (Auth.types.AuthContext): Authentication context.
        value (dict, optional): Additional request data.

    Returns:
        bool: True if authorized, False otherwise.
    """
    if not ctx.user or not getattr(ctx.user, "is_authenticated", False):
        return False
    return True
