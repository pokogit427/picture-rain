from datetime import date, datetime

from typing import Any

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


class EntitlementResponse(BaseModel):
    plan_code: str
    plan_status: str
    billing_enabled: bool
    daily_rounds_per_connection: int
    total_rounds_per_account: int


class UsageResponse(BaseModel):
    usage_date: date
    connection_used: int
    connection_limit: int
    account_used: int
    account_limit: int


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


class InputAssetResponse(BaseModel):
    id: str
    content_type: str
    size: int
    width: int
    height: int
    created_at: datetime
    url: str


class DraftResponse(BaseModel):
    id: str
    round_id: str
    version: int
    document: dict[str, Any]
    preview: InputAssetResponse | None
    updated_at: datetime
    expires_at: datetime


class SubmissionResponse(BaseModel):
    id: str
    round_id: str
    status: str
    result: InputAssetResponse
    submitted_at: datetime


class ResultResponse(BaseModel):
    submission_id: str
    is_mine: bool
    visibility: str
    content_type: str
    size: int
    width: int
    height: int
    submitted_at: datetime
    url: str


class HistoryItem(BaseModel):
    entry_id: str
    connection_id: str
    round_id: str
    submission_id: str
    is_mine: bool
    content_type: str
    size: int
    width: int
    height: int
    submitted_at: datetime
    revealed_at: datetime
    url: str


class HistoryTrashItem(HistoryItem):
    deleted_at: datetime
    purge_at: datetime


class HistoryDeleteRequest(BaseModel):
    entry_ids: list[str] = Field(min_length=1, max_length=100)


class InboxItem(BaseModel):
    round_id: str
    connection_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    input: InputAssetResponse
