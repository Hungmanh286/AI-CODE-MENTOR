from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import structlog
from jose import JWTError, jwt

from app.core.config import settings
from app.schemas import UserToken

logger = structlog.get_logger(__name__)

# bcrypt hashes at most the first 72 bytes of a password; longer input raises.
BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    """Encode a password for bcrypt, truncated to the 72 bytes bcrypt reads."""
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))
    except ValueError:  # malformed hash in storage
        logger.info("Stored password hash is not a valid bcrypt hash")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt (same `$2b$12$` format as the previous passlib setup)."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token with expiration and issued at timestamp

    Args:
        data (dict): Data to encode in the token
        expires_delta (Optional[timedelta]): Expiration time delta, defaults to 3 days

    Returns:
        str: Encoded JWT token
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    to_encode = data.copy()
    current_time = datetime.now(timezone.utc)

    to_encode["iat"] = int(current_time.timestamp())

    if expires_delta:
        expire = current_time + expires_delta
    else:
        expire = current_time + timedelta(days=3)
    to_encode["exp"] = int(expire.timestamp())

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.info(f"Failed to create JWT token: {str(e)}")
        raise


def verify_access_token(token: str) -> Optional[dict]:
    """
    Verify and decode JWT access token

    Args:
        token (str): JWT token to verify

    Returns:
        dict: Decoded payload if token is valid, None otherwise
    """
    if not token or not isinstance(token, str):
        logger.info("Invalid token format provided")
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.info(f"Unexpected error during token verification: {str(e)}")
        return None


if __name__ == "__main__":
    # import argparse

    # parser = argparse.ArgumentParser(description="Generate hash password from plain text string")
    # parser.add_argument("--pwd", dest="pwd", type=str, help="Plain text password")
    # args = parser.parse_args()
    # logger.info(get_password_hash(args.pwd))
    user_token = UserToken(
        user_id="000005",
        username="tester03",
        token_limit=1000000000,
    )

    logger.info(create_access_token(user_token.model_dump()))
