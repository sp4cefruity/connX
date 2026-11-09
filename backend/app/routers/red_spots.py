from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_or_create_user
from app.database import get_db
from app.models import SavedLocation, User, utcnow
from app.schemas import RedSpot, RedSpotCreate, RedSpotUpdate

router = APIRouter(prefix="/api/red-spots", tags=["red-spots"])


def get_active_red_spots(db: Session, user_id: str) -> list[SavedLocation]:
    """Red spots belonging to the user that haven't expired (spec §22 temporary red spots)."""
    now = utcnow()
    return (
        db.query(SavedLocation)
        .filter(SavedLocation.user_id == user_id)
        .filter(or_(SavedLocation.temporary.is_(False), SavedLocation.expires_at > now))
        .all()
    )


@router.get("", response_model=list[RedSpot])
def list_red_spots(db: Session = Depends(get_db), user: User = Depends(get_or_create_user)):
    return get_active_red_spots(db, user.id)


@router.post("", response_model=RedSpot, status_code=201)
def create_red_spot(
    payload: RedSpotCreate, db: Session = Depends(get_db), user: User = Depends(get_or_create_user)
):
    spot = SavedLocation(
        user_id=user.id,
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_m=payload.radius_m,
        type=payload.type,
        temporary=payload.temporary,
        expires_at=payload.expires_at,
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    return spot


@router.put("/{spot_id}", response_model=RedSpot)
def update_red_spot(
    spot_id: str,
    payload: RedSpotUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_or_create_user),
):
    spot = db.query(SavedLocation).filter_by(id=spot_id, user_id=user.id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Red spot not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(spot, field, value)

    db.commit()
    db.refresh(spot)
    return spot


@router.delete("/{spot_id}", status_code=204)
def delete_red_spot(spot_id: str, db: Session = Depends(get_db), user: User = Depends(get_or_create_user)):
    spot = db.query(SavedLocation).filter_by(id=spot_id, user_id=user.id).first()
    if not spot:
        raise HTTPException(status_code=404, detail="Red spot not found")
    db.delete(spot)
    db.commit()
    return None
