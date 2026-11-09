"""
Data models per spec §40.

Only User and SavedLocation ("red spots") are persisted for the MVP —
routes and comparisons are computed on demand and returned directly to
the client rather than written to the DB, which keeps the privacy story
simple (nothing about *where you went* is stored, only the *places you
asked to avoid*, which you created yourself). RouteComparison is still
modelled here so Phase 2 "route history" (spec §44) has somewhere to go.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    """Naive UTC now (columns are timezone-naive); avoids deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """
    Anonymous user. No email/password — see app/auth.py. Just an opaque
    id issued via cookie so red spots can be scoped to a device without
    requiring an account (spec §23 privacy-first).
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=utcnow)

    saved_locations = relationship("SavedLocation", back_populates="user", cascade="all, delete-orphan")


class SavedLocation(Base):
    """A "red spot" — a point + radius the user wants routes to avoid."""
    __tablename__ = "saved_locations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(120), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Float, nullable=False, default=100.0)
    type = Column(String(40), nullable=True)  # "home" | "office" | "school" | "other" ...

    temporary = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="saved_locations")


class RouteComparison(Base):
    """
    Optional persisted record of a comparison result, for Phase 2 route
    history (spec §44). Not written to by the MVP endpoints.
    """
    __tablename__ = "route_comparisons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    route_a_start = Column(String(255))
    route_a_end = Column(String(255))
    route_b_start = Column(String(255))
    route_b_end = Column(String(255))

    overlap_distance_m = Column(Float)
    overlap_percentage = Column(Float)
    overlap_duration_s = Column(Float)

    created_at = Column(DateTime, default=utcnow)
