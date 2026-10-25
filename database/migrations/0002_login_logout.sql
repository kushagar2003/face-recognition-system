-- Migration 0002: add logout time and duration to attendance.
--
-- check_in_at is the login time. logout_at is set later by a logout scan.
-- duration is calculated by the database; it stays empty until logout.
-- Existing rows are kept as they are (logout_at starts empty).

ALTER TABLE attendance
    ADD COLUMN IF NOT EXISTS logout_at TIMESTAMPTZ;

ALTER TABLE attendance
    ADD COLUMN IF NOT EXISTS duration INTERVAL
    GENERATED ALWAYS AS (logout_at - check_in_at) STORED;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'logout_not_before_login'
    ) THEN
        ALTER TABLE attendance
            ADD CONSTRAINT logout_not_before_login
            CHECK (logout_at IS NULL OR logout_at >= check_in_at);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_attendance_open
    ON attendance (session_id)
    WHERE logout_at IS NULL;

INSERT INTO schema_migrations (version)
VALUES ('0002_login_logout')
ON CONFLICT (version) DO NOTHING;
