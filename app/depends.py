from fastapi import Header, HTTPException, status

from app.schema import UserToken
from app.services import verify_access_token


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
