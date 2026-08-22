-- Run once against a fresh database (the compose file mounts this into
-- docker-entrypoint-initdb.d, so `docker compose up` gives you a working
-- schema with zero extra steps). Alembic can take over from here for
-- future migrations.
--
-- Deliberately plain PostgreSQL: all spatial math (overlap, red-spot
-- distance) runs in Python via Shapely, so no PostGIS extension is needed.
-- Column types match app/models.py exactly, so tables created here and by
-- SQLAlchemy's create_all are interchangeable.

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_locations (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    radius_m FLOAT NOT NULL DEFAULT 100,
    type VARCHAR(40),
    temporary BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_saved_locations_user
ON saved_locations (user_id);

CREATE TABLE IF NOT EXISTS route_comparisons (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    route_a_start VARCHAR(255),
    route_a_end VARCHAR(255),
    route_b_start VARCHAR(255),
    route_b_end VARCHAR(255),
    overlap_distance_m DOUBLE PRECISION,
    overlap_percentage DOUBLE PRECISION,
    overlap_duration_s DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);
