from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(Exception):
    """Email đã tồn tại trong hệ thống."""


class InvalidCredentialsError(Exception):
    """Email hoặc mật khẩu không đúng."""


async def register_user(db: AsyncSession, payload: UserCreate) -> User:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise EmailAlreadyRegisteredError(payload.email)

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Unique constraint trên users.email là lớp bảo vệ cuối chống race
        # condition: hai request đăng ký cùng email đồng thời đều pass bước
        # SELECT ở trên, request commit sau sẽ vi phạm unique constraint.
        await db.rollback()
        raise EmailAlreadyRegisteredError(payload.email) from None
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return user
