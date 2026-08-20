"""
Anonymous device identity, per spec §23 ("privacy-first... no accounts
required" is the landing page's own promise). Red spots need to be
scoped to *someone* without asking for an email/password, so we issue a
signed, random device id in an httpOnly cookie the first time a client
hits any endpoint that needs one, and use that as the user_id.

This is intentionally not "real" auth — there's no login, no password,
nothing to phish. Losing the cookie (clearing browser data, switching
devices) loses access to that device's saved red spots, which is the
correct privacy tradeoff for this product.
"""
import uuid

from fastapi import Cookie, Depends, Response
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

COOKIE_NAME = "connx_device"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().session_secret, salt="connx-device")


def get_or_create_user(
    response: Response,
    connx_device: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    s = _serializer()

    user_id: str | None = None
    if connx_device:
        try:
            user_id = s.loads(connx_device)
        except (BadSignature, ValueError):
            user_id = None

    user = db.get(User, user_id) if user_id else None

    if user is None:
        user = User()
        db.add(user)
        db.commit()
        db.refresh(user)
        response.set_cookie(
            COOKIE_NAME,
            s.dumps(user.id),
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,
        )

    return user
