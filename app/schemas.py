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


class InviteResponse(BaseModel):
    code: str
    expires_at: datetime


class ConnectionRequest(BaseModel):
    invite_code: str = Field(pattern=r"^\d{4}$")


class ConnectionResponse(BaseModel):
    id: str
    partner_user_id: str
    status: str
    created_at: datetime


class RoundCreateRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=32)


class RoundInputRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=32)


class RoundSummary(BaseModel):
    id: str
    connection_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    has_my_input: bool
    has_partner_input: bool


class RoundDetail(RoundSummary):
    my_asset_id: str | None
    partner_asset_id: str | None
