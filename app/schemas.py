from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    login_identifier: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    login_identifier: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    login_identifier: str
    status: str
    created_at: datetime
