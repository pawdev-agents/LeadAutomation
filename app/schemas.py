from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr, Field, field_validator
from .models import LeadStatus

class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    source: str = "manual"
    budget: int | None = Field(default=None, ge=0)
    service_type: str | None = None
    urgency: str | None = None
    utm_source: str | None = None; utm_medium: str | None = None; utm_campaign: str | None = None

class LeadUpdate(BaseModel):
    name: str | None=None; status: LeadStatus | None=None; owner_id: int | None=None
    budget: int | None=None; service_type: str | None=None; urgency: str | None=None

class LeadOut(BaseModel):
    id:int; name:str; email:EmailStr|None; phone:str|None; status:LeadStatus; score:int; owner_id:int|None; source_id:int|None; created_at:datetime
    class Config: from_attributes=True

class CaptureIn(LeadIn):
    website: str | None = None  # honeypot

class AppointmentIn(BaseModel):
    starts_at: datetime; ends_at: datetime; timezone: str = "UTC"
    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc_timestamp(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a UTC offset")
        return value.astimezone(timezone.utc)

class RegisterIn(BaseModel):
    team_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class NoteIn(BaseModel): text: str = Field(min_length=1, max_length=5000)
class UserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120); email: EmailStr; password: str = Field(min_length=8, max_length=128); role: str = "member"
class UserUpdateIn(BaseModel):
    name: str | None = None; role: str | None = None; active: bool | None = None
class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100); source_type: str = "other"; utm_defaults: dict = Field(default_factory=dict)
class SourceUpdateIn(BaseModel):
    name: str | None = None; source_type: str | None = None; utm_defaults: dict | None = None
class AppointmentCreateIn(BaseModel):
    lead_id: int; starts_at: datetime; ends_at: datetime | None = None; timezone: str = "UTC"
class AppointmentUpdateIn(BaseModel):
    starts_at: datetime | None = None; ends_at: datetime | None = None; status: str | None = None
class FollowupCreateIn(BaseModel):
    channel: str = "email"; subject: str | None = None; body: str | None = None; due_at: datetime
