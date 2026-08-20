-- Run once against a fresh database. Alembic can take over from here for
-- future migrations; this file exists so `docker compose up` gives you a
-- working schema with zero extra steps.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_locations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    radius_m DOUBLE PRECISION NOT NULL DEFAULT 100,
    type VARCHAR(40),
    temporary BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMP,
    geom GEOGRAPHY(POINT, 4326) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Spec §47: spatial index for red-spot lookups.
CREATE INDEX IF NOT EXISTS idx_saved_locations_geom
ON saved_locations
USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_saved_locations_user
ON saved_locations (user_id);

CREATE TABLE IF NOT EXISTS route_comparisons (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    route_a_start VARCHAR(255),
    route_a_end VARCHAR(255),
    route_b_start VARCHAR(255),
    route_b_end VARCHAR(255),
    overlap_distance_m DOUBLE PRECISION,
    overlap_percentage DOUBLE PRECISION,
    overlap_duration_s DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
