"""Pydantic schemas for team records and membership."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamCreate(BaseModel):
    team_name: str = Field(min_length=1, max_length=100)

    @field_validator("team_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class TeamUpdate(BaseModel):
    team_name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("team_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    team_name: str
    created_at: datetime


class TeamMemberCreate(BaseModel):
    player_id: int = Field(gt=0)


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    player_id: int
    joined_at: datetime
