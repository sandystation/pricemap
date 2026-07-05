-- Auth.js Postgres adapter schema (@auth/pg-adapter).
-- The adapter does NOT auto-create tables. Apply once to the `casaval` database:
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U casaval -d casaval < infra/postgres/auth-schema.sql
-- Also mounted at /docker-entrypoint-initdb.d so it runs automatically on a
-- fresh Postgres volume. IF NOT EXISTS keeps it idempotent / safe to re-run.

CREATE TABLE IF NOT EXISTS verification_token (
  identifier TEXT NOT NULL,
  expires TIMESTAMPTZ NOT NULL,
  token TEXT NOT NULL,
  PRIMARY KEY (identifier, token)
);

CREATE TABLE IF NOT EXISTS accounts (
  id SERIAL,
  "userId" INTEGER NOT NULL,
  type VARCHAR(255) NOT NULL,
  provider VARCHAR(255) NOT NULL,
  "providerAccountId" VARCHAR(255) NOT NULL,
  refresh_token TEXT,
  access_token TEXT,
  expires_at BIGINT,
  id_token TEXT,
  scope TEXT,
  session_state TEXT,
  token_type TEXT,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL,
  "userId" INTEGER NOT NULL,
  expires TIMESTAMPTZ NOT NULL,
  "sessionToken" VARCHAR(255) NOT NULL,
  PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS users (
  id SERIAL,
  name VARCHAR(255),
  email VARCHAR(255),
  "emailVerified" TIMESTAMPTZ,
  image TEXT,
  PRIMARY KEY (id)
);

-- === Credentials auth deltas (email/password) — idempotent =================
-- Password hash for credentials users; NULL for OAuth-only (Google) users.
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Case-insensitive unique email (register + authorize both use LOWER(email)).
-- The base DDL has no unique constraint on email, so add one.
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key ON users (LOWER(email));

-- The verification_token table above is REUSED for both flows: identifier is
-- namespaced 'verify:<email>' / 'reset:<email>', `token` stores sha256(raw) hex
-- (the raw token is emailed, never stored), `expires` carries the TTL (24h/1h).
-- Single-use consume = DELETE ... WHERE ... AND expires > now() RETURNING.
-- Housekeeping (optional cron): DELETE FROM verification_token WHERE expires < now();
