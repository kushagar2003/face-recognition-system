-- Migration 0003: one record for every live capture.
--
-- Every capture is kept, including ones with no face or several faces, so
-- the operator can review them. The roll number is stored as text on purpose:
-- a capture may be made before that student is enrolled.
-- The image itself stays on disk, in data/captures; only its relative path is stored.

CREATE TABLE IF NOT EXISTS captures (
    id           BIGSERIAL PRIMARY KEY,
    roll_number  TEXT NOT NULL
                 CHECK (roll_number ~ '^[A-Za-z0-9_-]{1,32}$'),
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    image_path   TEXT NOT NULL,
    face_count   INTEGER NOT NULL CHECK (face_count >= 0),
    status       TEXT NOT NULL
                 CHECK (status IN ('one_face', 'no_face', 'multiple_faces')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_captures_roll_time
    ON captures (roll_number, captured_at);

INSERT INTO schema_migrations (version)
VALUES ('0003_captures')
ON CONFLICT (version) DO NOTHING;
