from fastapi import Header, HTTPException, status

from app.core.security import verify_access_token
from app.schemas import UserToken


def validate_token_http(authorization: str = Header(...)):
    if not authorization.startswith("Bearer"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ")[1]
    try:
        user_dict = verify_access_token(token=token)
        user_token = UserToken.model_validate(user_dict)
        return user_token
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
