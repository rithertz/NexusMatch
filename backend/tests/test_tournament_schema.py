"""Unit tests for tournament request validation."""

import pytest
from app.schemas.tournament import TournamentCreate, TournamentUpdate
from pydantic import ValidationError


def tournament_payload(**overrides):
    return {
        "name": "Nexus Cup",
        "game_name": "Valorant",
        "tournament_type": "individual",
        "format": "single_elimination",
        "max_entries": 8,
        **overrides,
    }


def test_tournament_name_is_required():
    payload = tournament_payload()
    del payload["name"]

    with pytest.raises(ValidationError, match="name"):
        TournamentCreate(**payload)


@pytest.mark.parametrize("name", ["", "   ", "\t  \n"])
def test_tournament_name_rejects_blank_values(name):
    with pytest.raises(ValidationError):
        TournamentCreate(**tournament_payload(name=name))


def test_tournament_name_is_trimmed():
    tournament = TournamentCreate(**tournament_payload(name="  Nexus Cup  "))

    assert tournament.name == "Nexus Cup"


def test_tournament_name_rejects_more_than_150_characters():
    with pytest.raises(ValidationError, match="150"):
        TournamentCreate(**tournament_payload(name="N" * 151))


def test_tournament_name_accepts_150_characters():
    tournament = TournamentCreate(**tournament_payload(name="N" * 150))

    assert len(tournament.name) == 150


def test_tournament_name_is_trimmed_before_maximum_length_validation():
    tournament = TournamentCreate(
        **tournament_payload(name=f" {'N' * 150} ")
    )

    assert tournament.name == "N" * 150


def test_tournament_update_trims_name_before_maximum_length_validation():
    tournament = TournamentUpdate(name=f" {'N' * 150} ")

    assert tournament.name == "N" * 150
