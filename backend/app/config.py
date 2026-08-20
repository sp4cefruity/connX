"""
Centralised app settings, loaded from environment variables / .env.

Nothing here is secret by design except SESSION_SECRET — the whole point
of the routing-provider abstraction (see app/routing/base.py) is that
provider choice and API endpoints are config, not code.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://connx:connx@localhost:5432/connx"

    routing_provider: str = "osrm"  # "osrm" | "mock"
    osrm_base_url: str = "https://router.project-osrm.org"

    geocoding_provider: str = "nominatim"  # "nominatim" | "mock"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "ConnX/0.1 (dev)"

    frontend_origin: str = "http://localhost:3000"
    session_secret: str = "change-me-in-production"

    # Overlap detection defaults (spec §7, §30)
    default_overlap_tolerance_m: float = 50.0
    overlap_sensitivity_presets: dict = {"low": 20.0, "medium": 50.0, "high": 100.0}

    # Below this length, a shared segment is treated as an incidental
    # crossing rather than a meaningful overlap (spec §31).
    min_meaningful_overlap_m: float = 20.0

    # Overlap segments separated by less than this gap get merged into one
    # (spec §31 "multiple route segments").
    overlap_merge_gap_m: float = 25.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
