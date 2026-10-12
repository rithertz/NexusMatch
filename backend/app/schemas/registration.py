"""Pydantic schemas for tournament registrations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RegistrationStatus = Literal["pending", "approved", "rejected", "withdrawn"]


class RegistrationCreate(BaseModel):
    tournament_id: int = Field(gt=0)
    player_id: int | None = Field(default=None, gt=0)
    team_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_competitor(self):
        if (self.player_id is None) == (self.team_id is None):
            raise ValueError(
                "Provide exactly one of player_id or team_id."
            )
        return self


class RegistrationStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    tournament_id: int
    player_id: int | None
    team_id: int | None
    status: RegistrationStatus
    registered_at: datetime
