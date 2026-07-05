-- Comparables source: geo-located listings for spatial (ST_DWithin) queries.
-- Requires PostGIS (the postgres service uses the postgis/postgis image).
-- Idempotent. Apply after switching to the PostGIS image:
--   docker compose -f docker-compose.prod.yml exec -T postgres \
--     psql -U casaval -d casaval < infra/postgres/listings-schema.sql
-- Then load rows (geom is auto-derived from lat/lon):
--   \copy listings (external_id,source,listing_type,property_type,locality,lat,lon,
--     area_sqm,bedrooms,price_eur,price_per_sqm,url,listing_date) FROM 'mt_listings.csv' CSV HEADER

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS listings (
  id SERIAL PRIMARY KEY,
  external_id TEXT,
  source TEXT,
  listing_type TEXT,
  property_type TEXT,
  locality TEXT,
  lat DOUBLE PRECISION NOT NULL,
  lon DOUBLE PRECISION NOT NULL,
  area_sqm DOUBLE PRECISION,
  bedrooms INTEGER,
  price_eur DOUBLE PRECISION,
  price_per_sqm DOUBLE PRECISION,
  url TEXT,
  listing_date DATE,
  -- Derived point (immutable expr → STORED generated column), GiST-indexed.
  geom geometry(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED
);

CREATE INDEX IF NOT EXISTS ix_listings_geom ON listings USING GIST (geom);
CREATE INDEX IF NOT EXISTS ix_listings_filter ON listings (listing_type, property_type, area_sqm);

-- Staging table for the daily refresh: the CSV is COPY'd here, then swapped into
-- `listings` inside one transaction so readers never see an empty table. Same data
-- columns as `listings`, minus the SERIAL id and the generated geom.
CREATE TABLE IF NOT EXISTS listings_staging (
  external_id TEXT,
  source TEXT,
  listing_type TEXT,
  property_type TEXT,
  locality TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  area_sqm DOUBLE PRECISION,
  bedrooms INTEGER,
  price_eur DOUBLE PRECISION,
  price_per_sqm DOUBLE PRECISION,
  url TEXT,
  listing_date DATE
);
