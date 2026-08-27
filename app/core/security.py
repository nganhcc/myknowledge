from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | Any, expires_delta: timedelta | None = None
) -> str:
    issued_at = datetime.now(UTC)
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "exp": expire,
        "iat": issued_at,
        "sub": str(subject),
        # Phân biệt loại token để về sau không nhầm refresh token với access token
        "type": "access",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> str | None:
    """Giải mã JWT và trả về subject (user id) nếu hợp lệ, ngược lại None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.InvalidTokenError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub is not None else None
