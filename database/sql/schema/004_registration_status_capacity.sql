
BEGIN;

-- Replace the registration trigger function with a version that
-- validates competitor type and capacity on every relevant change.

CREATE OR REPLACE FUNCTION validate_registration_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_tournament_type TEXT;
    v_max_entries INTEGER;
    v_active_count BIGINT;
BEGIN
    -- Serialize changes targeting the same tournament.
    SELECT tournament_type, max_entries
    INTO v_tournament_type, v_max_entries
    FROM tournaments
    WHERE tournament_id = NEW.tournament_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Tournament % does not exist',
            NEW.tournament_id;
    END IF;

    -- Validate individual/team competitor type.
    IF v_tournament_type = 'individual'
       AND NEW.player_id IS NULL THEN
        RAISE EXCEPTION
            'Individual tournaments require a player registration';
    END IF;

    IF v_tournament_type = 'team'
       AND NEW.team_id IS NULL THEN
        RAISE EXCEPTION
            'Team tournaments require a team registration';
    END IF;

    -- Only active registrations consume capacity.
    IF NEW.status IN ('pending', 'approved') THEN
        SELECT COUNT(*)
        INTO v_active_count
        FROM registrations
        WHERE tournament_id = NEW.tournament_id
          AND status IN ('pending', 'approved')
          AND registration_id IS DISTINCT FROM
              NEW.registration_id;

        IF v_active_count >= v_max_entries THEN
            RAISE EXCEPTION
                'Tournament % is full (capacity: %)',
                NEW.tournament_id,
                v_max_entries;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- Ensure status-only updates invoke the validation function.
DROP TRIGGER IF EXISTS trg_validate_registration_type
ON registrations;

CREATE TRIGGER trg_validate_registration_type
BEFORE INSERT OR UPDATE ON registrations
FOR EACH ROW
EXECUTE FUNCTION validate_registration_type();

COMMIT;
