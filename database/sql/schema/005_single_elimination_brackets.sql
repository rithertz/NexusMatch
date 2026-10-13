-- Extend the existing match model for persisted single-elimination brackets.
BEGIN;

ALTER TABLE matches
    ADD COLUMN is_bye BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE matches
    ADD CONSTRAINT match_bye_must_be_completed
    CHECK (NOT is_bye OR status = 'completed');

ALTER TABLE match_participants
    ADD COLUMN slot_number SMALLINT;

WITH participant_slots AS (
    SELECT
        match_id,
        registration_id,
        ROW_NUMBER() OVER (
            PARTITION BY match_id
            ORDER BY registration_id
        ) AS slot_number
    FROM match_participants
)
UPDATE match_participants AS participants
SET slot_number = participant_slots.slot_number
FROM participant_slots
WHERE participants.match_id = participant_slots.match_id
  AND participants.registration_id = participant_slots.registration_id;

ALTER TABLE match_participants
    ALTER COLUMN slot_number SET NOT NULL,
    ADD CONSTRAINT match_participant_slot_number_valid
        CHECK (slot_number IN (1, 2)),
    ADD CONSTRAINT match_participant_score_nonnegative
        CHECK (score IS NULL OR score >= 0);

CREATE UNIQUE INDEX uq_match_participants_match_slot
    ON match_participants (match_id, slot_number);

CREATE UNIQUE INDEX uq_match_participants_single_winner
    ON match_participants (match_id)
    WHERE is_winner;

CREATE FUNCTION prevent_registration_changes_after_bracket()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    target_tournament_id BIGINT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_tournament_id := OLD.tournament_id;

        -- Permit cascades from deleting a tournament while protecting direct
        -- registration deletions that would invalidate a generated bracket.
        IF pg_trigger_depth() > 1 THEN
            RETURN OLD;
        END IF;
    ELSE
        target_tournament_id := NEW.tournament_id;
    END IF;

    PERFORM 1
    FROM tournaments
    WHERE tournament_id = target_tournament_id
    FOR UPDATE;

    IF EXISTS (
        SELECT 1
        FROM matches
        WHERE tournament_id = target_tournament_id
    ) THEN
        RAISE EXCEPTION
            'Registrations cannot change after the tournament bracket is generated';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_registration_changes_after_bracket
BEFORE INSERT OR UPDATE OR DELETE ON registrations
FOR EACH ROW
EXECUTE FUNCTION prevent_registration_changes_after_bracket();

COMMIT;
