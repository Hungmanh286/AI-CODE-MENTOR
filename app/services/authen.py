import structlog

from typing import Any, List, Tuple

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt

from app.services.gentoken import verify_password
from app.error import UnauthorizedException
from app.schema.authen import UserInDB
from app.config import settings


logger = structlog.get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={"user": "Current user", "admin": "Supper grant"},
)


def get_user(db: Any, username: str) -> UserInDB:
    """Get user info from json schema"""
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def jwt_decode(token_str: str) -> Tuple[UserInDB, List]:
    """Decode JWT token string"""
    try:
        payload = jwt.decode(
            token=token_str, key=settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("sub")
        token_scopes = payload.get("scopes")
        user_info = None
        if username:
            user_info = get_user(settings._accounts, username=username)
        return user_info, token_scopes
    except Exception as e:
        logger.info(e)
        return None, None


async def decrypt_token(
    security_scopes: SecurityScopes, token_str: str = Depends(oauth2_scheme)
) -> UserInDB:
    """Decrypt token get user name and scope

    Parameters
    ----------
        - security_scopes : list scopes for api
        - token_str : access token string

    Returns
    -------
        - current user from token
    """
    authenticate_value = (
        security_scopes.scopes
        and f'Bearer scope="{security_scopes.scope_str}"'
        or "Bearer"
    )
    credentials_exception = UnauthorizedException(
        headers={"WWW-Authenticate": authenticate_value},
    )
    user_info, token_scopes = jwt_decode(token_str=token_str)
    if user_info is None:
        raise credentials_exception
    if user_info.disabled:
        raise UnauthorizedException(detail="Inactive user")
    for scope in token_scopes:
        if scope in security_scopes.scopes:
            return user_info
    raise credentials_exception
