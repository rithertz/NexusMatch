"""Pydantic schemas for player profiles."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlayerCreate(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=100)
    email: str | None = None

    @field_validator("username", "display_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        return value


class PlayerUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=40)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = None

    @field_validator("username", "display_name")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        return value


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    username: str
    display_name: str
    email: str | None
    created_at: datetime
