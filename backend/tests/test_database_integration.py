
"""Integration tests for NexusMatch PostgreSQL constraints and triggers."""

import os
import uuid

import psycopg
import pytest


@pytest.fixture
def db():
    """Run each test in a transaction and roll back its test data."""
    dsn = os.getenv("NEXUSMATCH_TEST_DATABASE_URL")

    if not dsn:
        pytest.skip("Set NEXUSMATCH_TEST_DATABASE_URL to run database tests")

    with psycopg.connect(dsn) as connection:
        try:
            with connection.transaction():
                yield connection
                # Force rollback instead of committing test data.
                raise _RollbackTestTransaction
        except _RollbackTestTransaction:
            pass


class _RollbackTestTransaction(Exception):
    """Internal signal used to roll back a test transaction."""


@pytest.fixture
def suffix():
    """Generate unique names so tests don't collide."""
    return uuid.uuid4().hex[:12]


def create_player(db, suffix, label="player"):
    row = db.execute(
        """
        INSERT INTO players (username, display_name)
        VALUES (%s, %s)
        RETURNING player_id
        """,
        (f"{label}_{suffix}", f"Test {label}"),
    ).fetchone()
    return row[0]


def create_team(db, suffix):
    row = db.execute(
        """
        INSERT INTO teams (team_name)
        VALUES (%s)
        RETURNING team_id
        """,
        (f"team_{suffix}",),
    ).fetchone()
    return row[0]


def create_tournament(db, suffix, tournament_type="individual", capacity=8):
    row = db.execute(
        """
        INSERT INTO tournaments
            (name, game_name, tournament_type, format, max_entries)
        VALUES (%s, 'Integration Test Game', %s, 'swiss', %s)
        RETURNING tournament_id
        """,
        (f"tournament_{suffix}", tournament_type, capacity),
    ).fetchone()
    return row[0]


def create_registration(db, tournament_id, *, player_id=None, team_id=None):
    row = db.execute(
        """
        INSERT INTO registrations (tournament_id, player_id, team_id)
        VALUES (%s, %s, %s)
        RETURNING registration_id
        """,
        (tournament_id, player_id, team_id),
    ).fetchone()
    return row[0]


def test_valid_individual_registration(db, suffix):
    player_id = create_player(db, suffix)
    tournament_id = create_tournament(db, suffix)

    registration_id = create_registration(
        db, tournament_id, player_id=player_id
    )

    assert registration_id is not None


def test_valid_team_registration(db, suffix):
    team_id = create_team(db, suffix)
    tournament_id = create_tournament(
        db, suffix, tournament_type="team"
    )

    registration_id = create_registration(
        db, tournament_id, team_id=team_id
    )

    assert registration_id is not None


def test_mismatched_competitor_type_is_rejected(db, suffix):
    team_id = create_team(db, suffix)
    tournament_id = create_tournament(db, suffix)

    with pytest.raises(psycopg.Error, match="Individual tournaments require"):
        create_registration(db, tournament_id, team_id=team_id)


def test_cross_tournament_match_participant_is_rejected(db, suffix):
    player_id = create_player(db, suffix)
    individual_tournament_id = create_tournament(db, suffix)
    team_tournament_id = create_tournament(
        db, f"{suffix}_other", tournament_type="team"
    )
    team_id = create_team(db, suffix)

    individual_registration_id = create_registration(
        db, individual_tournament_id, player_id=player_id
    )
    create_registration(db, team_tournament_id, team_id=team_id)

    match_id = db.execute(
        """
        INSERT INTO matches (tournament_id, round_number, match_number)
        VALUES (%s, 1, 1)
        RETURNING match_id
        """,
        (team_tournament_id,),
    ).fetchone()[0]

    with pytest.raises(
        psycopg.errors.ForeignKeyViolation,
        match="match_participants_registration_id_tournament_id_fkey",
    ):
        db.execute(
            """
            INSERT INTO match_participants
                (match_id, tournament_id, registration_id)
            VALUES (%s, %s, %s)
            """,
            (
                match_id,
                team_tournament_id,
                individual_registration_id,
            ),
        )


def test_registration_capacity_is_enforced(db, suffix):
    tournament_id = create_tournament(db, suffix, capacity=2)

    for index in range(3):
        player_id = create_player(db, suffix, label=f"capacity{index}")

        if index < 2:
            create_registration(db, tournament_id, player_id=player_id)
        else:
            with pytest.raises(psycopg.Error, match="is full"):
                create_registration(
                    db, tournament_id, player_id=player_id
                )


def test_incompatible_tournament_type_change_is_rejected(db, suffix):
    player_id = create_player(db, suffix)
    tournament_id = create_tournament(db, suffix)
    create_registration(db, tournament_id, player_id=player_id)

    with pytest.raises(
        psycopg.Error,
        match="Cannot change tournament type",
    ):
        db.execute(
            """
            UPDATE tournaments
            SET tournament_type = 'team'
            WHERE tournament_id = %s
            """,
            (tournament_id,),
        )


def test_capacity_cannot_be_lowered_below_active_registrations(db, suffix):
    tournament_id = create_tournament(db, suffix, capacity=4)

    # Create three active registrations.
    for index in range(3):
        player_id = create_player(db, suffix, label=f"active{index}")
        create_registration(db, tournament_id, player_id=player_id)

    # Capacity cannot be reduced from 4 to 2 while 3 registrations are active.
    with pytest.raises(
        psycopg.Error,
        match="Capacity cannot be lower than active registrations",
    ):
        db.execute(
            """
            UPDATE tournaments
            SET max_entries = 2
            WHERE tournament_id = %s
            """,
            (tournament_id,),
        )
