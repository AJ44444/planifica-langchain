from typing import TypedDict

class GoogleIdTokenPayload(TypedDict, total=False):
    sub: str
    email: str
    name: str
    given_name: str
    family_name: str
    picture: str
    aud: str
    iss: str
    exp: int
    iat: int


class JWTAccessTokenPayload(TypedDict, total=False):
    sub: str
    email: str
    nombres: str
    rol: str
    type: str
    iat: int
    exp: int


class SessionUserDict(TypedDict):
    id_usuario: str
    email: str
    nombres: str
    rol: str


class SessionResponseDict(TypedDict):
    session_id: str
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: SessionUserDict
