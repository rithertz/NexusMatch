"""Pydantic schemas for tournament endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TournamentType = Literal["individual", "team"]
TournamentFormat = Literal["single_elimination", "double_elimination", "round_robin", "swiss"]
TournamentStatus = Literal[
    "draft", "registration_open", "in_progress", "completed", "cancelled"
]


class TournamentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    game_name: str = Field(min_length=1, max_length=100)
    tournament_type: TournamentType
    format: TournamentFormat
    max_entries: int = Field(ge=2, le=100_000)
    starts_at: datetime | None = None

    @field_validator("name", "game_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class TournamentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=150)
    game_name: str | None = Field(default=None, min_length=1, max_length=100)
    format: TournamentFormat | None = None
    max_entries: int | None = Field(default=None, ge=2, le=100_000)
    starts_at: datetime | None = None
    status: TournamentStatus | None = None

    @field_validator("name", "game_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value


class TournamentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tournament_id: int
    name: str
    game_name: str
    tournament_type: TournamentType
    format: TournamentFormat
    status: TournamentStatus
    max_entries: int
    starts_at: datetime | None
    created_at: datetime
