-- App tables (non-auth) for the casaval database. Idempotent; safe to re-run.
-- Apply the same way as auth-schema.sql:
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U casaval -d casaval < infra/postgres/app-schema.sql
-- Also mounted at /docker-entrypoint-initdb.d so it runs on a fresh volume.

-- Saved valuation history — one row per completed valuation for a logged-in user.
-- input/result hold the full form payload + model response; the flat columns are
-- denormalized for fast list rendering.
CREATE TABLE IF NOT EXISTS saved_valuations (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  address TEXT,
  listing_type VARCHAR(16),
  property_type VARCHAR(32),
  area_sqm DOUBLE PRECISION,
  estimate_eur DOUBLE PRECISION,
  input JSONB NOT NULL,
  result JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_saved_valuations_user
  ON saved_valuations (user_id, created_at DESC);
