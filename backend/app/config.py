"""
Centralised app settings, loaded from environment variables / .env.

Nothing here is secret by design except SESSION_SECRET - the whole point
of the routing-provider abstraction (see app/routing/base.py) is that
provider choice and API endpoints are config, not code.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env file relative to THIS file (backend/.env), not the
# process working directory. Otherwise tools that run from the repo root
# (run_all.py) can't see backend/.env and silently fall back to defaults.
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://connx:connx@localhost:5432/connx"

    routing_provider: str = "ors"  # "ors" (OSRM fallback) | "osrm" | "mock"
    # OpenRouteService free tier: 2,000 directions/day, 40/min. Without a key
    # "ors" quietly degrades to OSRM only (ADR 0005).
    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org"
    route_cache_ttl_s: float = 3600.0
    route_cache_max_entries: int = 500
    # One OSRM server per mode: a server has a single baked-in profile and
    # ignores the profile in the URL (ADR 0002).
    osrm_driving_base_url: str = "https://routing.openstreetmap.de/routed-car"
    osrm_walking_base_url: str = "https://routing.openstreetmap.de/routed-foot"
    osrm_cycling_base_url: str = "https://routing.openstreetmap.de/routed-bike"

    geocoding_provider: str = "photon"  # "photon" (Nominatim fallback) | "nominatim" | "mock"
    photon_base_url: str = "https://photon.komoot.io"
    photon_timeout_s: float = 3.0
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "ConnX/0.1 (dev)"

    # "development" | "production" - controls CORS strategy below (see main.py).
    # In dev, every teammate's `npm run dev` can land on a different port
    # (3000 is just Next's default; it silently bumps to 3001+ if taken), so
    # CORS is matched by a localhost/127.0.0.1 regex instead of one fixed
    # origin. That regex is intentionally NOT used in production - there we
    # lock down to the exact deployed frontend origin(s) below.
    environment: str = "development"

    frontend_origin: str = "http://localhost:3000"
    session_secret: str = "change-me-in-production"

    # Overlap tolerance: how close counts as "the same road". Fixed, not
    # user-set, and deliberately separate from the user's danger distance
    # (ADR 0001).
    overlap_tolerance_m: float = 25.0

    # Below this length, a shared segment is treated as an incidental
    # crossing rather than a meaningful overlap (spec section 31).
    min_meaningful_overlap_m: float = 20.0

    # Overlap segments separated by less than this gap get merged into one
    # (spec section 31, "multiple route segments").
    overlap_merge_gap_m: float = 25.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
