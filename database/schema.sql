-- Face Recognition Attendance System: database schema (version 0001).
--
-- Safe to run more than once: every statement uses IF NOT EXISTS, and nothing
-- is dropped. Run it through: python -m database.init_db
--
-- Privacy notes:
--   * No raw face images are stored in any table.
--   * face_embeddings holds biometric data. Treat it as sensitive.
--   * audit_logs must never contain embeddings, images, passwords or tokens.

-- ---------------------------------------------------------------------------
-- Migration bookkeeping
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Administrator accounts (used by the backend login, Step 3)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id             BIGSERIAL PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,              -- an Argon2 or bcrypt hash, never plain text
    role           TEXT NOT NULL DEFAULT 'admin'
                   CHECK (role IN ('admin', 'viewer')),
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Enrolled people
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS persons (
    id                  BIGSERIAL PRIMARY KEY,
    person_code         TEXT NOT NULL UNIQUE,     -- internal ID, not a national ID
    full_name           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive')),
    consent_recorded_at TIMESTAMPTZ NOT NULL,     -- consent is required before enrolment
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Face embeddings (biometric data). One person can have several.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS face_embeddings (
    id             BIGSERIAL PRIMARY KEY,
    person_id      BIGINT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    embedding      REAL[] NOT NULL,
    dimension      INTEGER NOT NULL CHECK (dimension > 0),
    model_name     TEXT NOT NULL,                 -- for example 'sface'
    model_version  TEXT NOT NULL,                 -- the exact model file version
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The stored array length must match the declared dimension.
    CONSTRAINT embedding_length_matches
        CHECK (cardinality(embedding) = dimension)
);

CREATE INDEX IF NOT EXISTS idx_face_embeddings_person
    ON face_embeddings (person_id);

-- Only compare embeddings made by the same model and version.
CREATE INDEX IF NOT EXISTS idx_face_embeddings_model
    ON face_embeddings (model_name, model_version);

-- ---------------------------------------------------------------------------
-- Attendance sessions (a class, shift, or event that people check in to)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    starts_at   TIMESTAMPTZ NOT NULL,
    ends_at     TIMESTAMPTZ NOT NULL,
    is_open     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT session_ends_after_start CHECK (ends_at > starts_at)
);

-- ---------------------------------------------------------------------------
-- Attendance records
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance (
    id           BIGSERIAL PRIMARY KEY,
    person_id    BIGINT NOT NULL REFERENCES persons(id) ON DELETE RESTRICT,
    session_id   BIGINT NOT NULL REFERENCES sessions(id) ON DELETE RESTRICT,
    check_in_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status       TEXT NOT NULL DEFAULT 'present'
                 CHECK (status IN ('present')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The database itself blocks a second check-in for the same person and
    -- session, even if two requests arrive at the same moment.
    CONSTRAINT one_checkin_per_session UNIQUE (person_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_person_time
    ON attendance (person_id, check_in_at);

CREATE INDEX IF NOT EXISTS idx_attendance_session
    ON attendance (session_id);

-- ---------------------------------------------------------------------------
-- Audit log: who did what. Never store biometric data or secrets here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id           BIGSERIAL PRIMARY KEY,
    actor_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action       TEXT NOT NULL,                  -- for example 'person.register'
    entity_type  TEXT NOT NULL,                  -- for example 'persons'
    entity_id    TEXT,
    details      JSONB,                          -- small, non-sensitive metadata only
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created
    ON audit_logs (created_at);

-- ---------------------------------------------------------------------------
-- Record that this version has been applied
-- ---------------------------------------------------------------------------
INSERT INTO schema_migrations (version)
VALUES ('0001_initial')
ON CONFLICT (version) DO NOTHING;
