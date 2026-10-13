"""Pydantic schemas for bracket retrieval and match results."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MatchStatus = Literal["scheduled", "in_progress", "completed", "cancelled"]
CompetitorType = Literal["player", "team"]


class BracketParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    registration_id: int
    slot_number: int
    competitor_type: CompetitorType
    competitor_id: int
    display_name: str
    score: Decimal | None
    is_winner: bool


class BracketMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: int
    round_number: int
    match_number: int
    status: MatchStatus
    is_bye: bool
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    winner_registration_id: int | None
    participants: list[BracketParticipantResponse]


class BracketRoundResponse(BaseModel):
    round_number: int
    matches: list[BracketMatchResponse]


class BracketResponse(BaseModel):
    tournament_id: int
    rounds: list[BracketRoundResponse]


class MatchScore(BaseModel):
    registration_id: int = Field(gt=0)
    score: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class MatchResultCreate(BaseModel):
    winner_registration_id: int = Field(gt=0)
    scores: list[MatchScore] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_scores_and_winner(self) -> Self:
        registration_ids = [item.registration_id for item in self.scores]
        if len(set(registration_ids)) != 2:
            raise ValueError("Scores must be provided for two distinct registrations.")

        if self.scores[0].score == self.scores[1].score:
            raise ValueError("A match result must not be tied.")

        highest_score = max(self.scores, key=lambda item: item.score)
        if highest_score.registration_id != self.winner_registration_id:
            raise ValueError("The winner must have the higher submitted score.")

        return self
