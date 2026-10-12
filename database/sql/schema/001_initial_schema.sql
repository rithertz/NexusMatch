-- NexusMatch: initial relational schema
-- PostgreSQL 17
-- Apply to a fresh database only.

BEGIN;

CREATE TABLE players (
    player_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(40) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE teams (
    team_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE team_members (
    team_id BIGINT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    player_id BIGINT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (team_id, player_id)
);

CREATE TABLE tournaments (
    tournament_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    game_name VARCHAR(100) NOT NULL,
    tournament_type VARCHAR(10) NOT NULL
        CHECK (tournament_type IN ('individual', 'team')),
    format VARCHAR(20) NOT NULL
        CHECK (format IN (
            'single_elimination',
            'double_elimination',
            'round_robin',
            'swiss'
        )),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft',
            'registration_open',
            'in_progress',
            'completed',
            'cancelled'
        )),
    max_entries INTEGER NOT NULL CHECK (max_entries >= 2),
    starts_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE registrations (
    registration_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tournament_id BIGINT NOT NULL
        REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    player_id BIGINT REFERENCES players(player_id),
    team_id BIGINT REFERENCES teams(team_id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT registration_exactly_one_competitor
        CHECK ((player_id IS NOT NULL) <> (team_id IS NOT NULL)),

    CONSTRAINT registration_player_unique
        UNIQUE (tournament_id, player_id),

    CONSTRAINT registration_team_unique
        UNIQUE (tournament_id, team_id),

    CONSTRAINT registration_id_tournament_unique
        UNIQUE (registration_id, tournament_id)
);

CREATE FUNCTION validate_registration_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    expected_type VARCHAR(10);
BEGIN
    SELECT tournament_type
    INTO expected_type
    FROM tournaments
    WHERE tournament_id = NEW.tournament_id;

    IF expected_type = 'individual' AND NEW.player_id IS NULL THEN
        RAISE EXCEPTION 'Individual tournaments require a player registration';
    END IF;

    IF expected_type = 'team' AND NEW.team_id IS NULL THEN
        RAISE EXCEPTION 'Team tournaments require a team registration';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_registration_type
BEFORE INSERT OR UPDATE OF tournament_id, player_id, team_id
ON registrations
FOR EACH ROW
EXECUTE FUNCTION validate_registration_type();

CREATE TABLE matches (
    match_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tournament_id BIGINT NOT NULL
        REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL CHECK (round_number >= 1),
    match_number INTEGER NOT NULL CHECK (match_number >= 1),
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    scheduled_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tournament_id, round_number, match_number),
    UNIQUE (match_id, tournament_id)
);

CREATE TABLE match_participants (
    match_id BIGINT NOT NULL,
    tournament_id BIGINT NOT NULL,
    registration_id BIGINT NOT NULL,
    score NUMERIC(10, 2),
    placement INTEGER CHECK (placement >= 1),
    is_winner BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (match_id, registration_id),

    FOREIGN KEY (match_id, tournament_id)
        REFERENCES matches(match_id, tournament_id) ON DELETE CASCADE,

    FOREIGN KEY (registration_id, tournament_id)
        REFERENCES registrations(registration_id, tournament_id) ON DELETE CASCADE
);

CREATE INDEX idx_registrations_tournament_status
    ON registrations(tournament_id, status);

CREATE INDEX idx_matches_tournament_round
    ON matches(tournament_id, round_number);

CREATE INDEX idx_match_participants_registration
    ON match_participants(registration_id);

COMMIT;
