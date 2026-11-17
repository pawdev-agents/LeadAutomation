import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db
from ..models import Team, User
from ..services.team_settings import merged
from .users import admin

router = APIRouter(prefix="/settings", tags=["settings"])
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
SETTING_KEYS = (
    "scoring_weights",
    "followup_delays_days",
    "auto_reply_subject",
    "auto_reply_body",
    "working_hours",
)


class WorkingHours(BaseModel):
    start: str
    end: str
    days: list[int] = Field(min_length=1, max_length=7)

    @field_validator("start", "end")
    @classmethod
    def valid_time(cls, value):
        if not TIME.match(value):
            raise ValueError("Use HH:MM in 24-hour time")
        return value

    @field_validator("days")
    @classmethod
    def valid_days(cls, value):
        if any(d < 0 or d > 6 for d in value) or len(set(value)) != len(value):
            raise ValueError("Days must be unique numbers from 0 (Mon) to 6 (Sun)")
        return sorted(value)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("End must be after start")
        return self


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_name: str | None = Field(None, min_length=1, max_length=120)
    timezone: str | None = Field(None, min_length=1, max_length=64)
    scoring_weights: dict[str, int] | None = None
    followup_delays_days: list[int] | None = None
    auto_reply_subject: str | None = Field(None, max_length=200)
    auto_reply_body: str | None = Field(None, max_length=5000)
    working_hours: WorkingHours | None = None

    @field_validator("scoring_weights")
    @classmethod
    def valid_weights(cls, value):
        if value is None:
            return value
        if len(value) > 20 or any(len(k) > 40 for k in value):
            raise ValueError("At most 20 weights, names up to 40 characters")
        if any(v < 0 or v > 100 for v in value.values()):
            raise ValueError("Each weight must be between 0 and 100")
        return value

    @field_validator("followup_delays_days")
    @classmethod
    def valid_delays(cls, value):
        if value is None:
            return value
        if not 1 <= len(value) <= 5:
            raise ValueError("Use between 1 and 5 follow-up delays")
        if any(d < 1 or d > 90 for d in value):
            raise ValueError("Each delay must be between 1 and 90 days")
        if value != sorted(set(value)):
            raise ValueError("Delays must be increasing with no duplicates")
        return value


def output(team: Team) -> dict:
    return {"team_name": team.name, "timezone": team.timezone, **merged(team)}


@router.get("")
def get_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return output(db.get(Team, user.team_id))


@router.patch("")
def update_settings(data: SettingsPatch, db: Session = Depends(get_db), user: User = Depends(admin)):
    team = db.get(Team, user.team_id)
    values = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "team_name" in values:
        taken = db.scalar(select(Team).where(Team.name == values["team_name"], Team.id != team.id))
        if taken:
            raise HTTPException(409, "Team name is already in use")
        team.name = values["team_name"]
    if "timezone" in values:
        team.timezone = values["timezone"]
    current = dict(team.settings or {})
    for key in SETTING_KEYS:
        if key in values:
            current[key] = values[key]
    team.settings = current
    db.commit()
    db.refresh(team)
    return output(team)
