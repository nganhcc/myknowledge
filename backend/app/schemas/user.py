import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    # EmailStr yêu cầu dependency `email-validator`: kiểm tra cú pháp email
    # theo chuẩn (bắt buộc có @, domain hợp lệ...) thay vì chỉ check độ dài.
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
