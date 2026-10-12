
BEGIN;

CREATE OR REPLACE FUNCTION prevent_capacity_below_active_count()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_active_count BIGINT;
BEGIN
    IF NEW.max_entries < OLD.max_entries THEN
        -- Serialize capacity changes against registration attempts.
        PERFORM 1
        FROM tournaments
        WHERE tournament_id = OLD.tournament_id
        FOR UPDATE;

        SELECT COUNT(*)
        INTO v_active_count
        FROM registrations
        WHERE tournament_id = OLD.tournament_id
          AND status IN ('pending', 'approved');

        IF NEW.max_entries < v_active_count THEN
            RAISE EXCEPTION
                'Capacity cannot be lower than active registrations (active: %, requested: %)',
                v_active_count,
                NEW.max_entries;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_prevent_capacity_below_active_count
BEFORE UPDATE OF max_entries ON tournaments
FOR EACH ROW
EXECUTE FUNCTION prevent_capacity_below_active_count();

COMMIT;
