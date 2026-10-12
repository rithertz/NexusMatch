
BEGIN;

-- Replace the registration validation trigger function.
-- The tournament row lock serializes registration attempts
-- for the same tournament.

CREATE OR REPLACE FUNCTION validate_registration_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_tournament_type TEXT;
    v_max_entries INTEGER;
    v_active_count BIGINT;
BEGIN
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

    -- Enforce individual-versus-team registration rules.
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

    -- Pending and approved registrations consume slots.
    -- Rejected and withdrawn registrations do not.
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

-- Prevent changing a tournament's type if its existing
-- registrations would become invalid.

CREATE OR REPLACE FUNCTION prevent_incompatible_tournament_type_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.tournament_type <> OLD.tournament_type
       AND EXISTS (
           SELECT 1
           FROM registrations r
           WHERE r.tournament_id = OLD.tournament_id
             AND (
                 (NEW.tournament_type = 'individual'
                  AND r.player_id IS NULL)
                 OR
                 (NEW.tournament_type = 'team'
                  AND r.team_id IS NULL)
             )
       )
    THEN
        RAISE EXCEPTION
            'Cannot change tournament type while incompatible registrations exist';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_incompatible_tournament_type_change
BEFORE UPDATE OF tournament_type ON tournaments
FOR EACH ROW
EXECUTE FUNCTION prevent_incompatible_tournament_type_change();

COMMIT;
