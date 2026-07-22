from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth_dependency import get_current_admin
from database import SessionLocal
from models import AnnouncementSetting


router = APIRouter(tags=["Announcement Bar"])

DEFAULT_CONTENT = "Free Shipping on orders over 900 EGP"


class AnnouncementUpdate(BaseModel):
    content: str = Field(default="", max_length=600)
    is_active: bool = False


class AnnouncementResponse(BaseModel):
    id: int
    content: str
    is_active: bool
    updated_at: Optional[datetime] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_settings(db: Session) -> AnnouncementSetting:
    settings = db.query(AnnouncementSetting).filter(
        AnnouncementSetting.id == 1
    ).first()

    if settings:
        return settings

    settings = AnnouncementSetting(
        id=1,
        content=DEFAULT_CONTENT,
        is_active=True,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def serialize(settings: AnnouncementSetting) -> dict:
    return {
        "id": settings.id,
        "content": settings.content or "",
        "is_active": bool(settings.is_active),
        "updated_at": settings.updated_at,
    }


@router.get("/announcement", response_model=AnnouncementResponse)
def get_public_announcement(
    response: Response,
    db: Session = Depends(get_db),
):
    # Prevent an old announcement from remaining cached after the admin edits it.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    settings = get_or_create_settings(db)
    return serialize(settings)


@router.get("/admin/announcement", response_model=AnnouncementResponse)
def get_admin_announcement(
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    response.headers["Cache-Control"] = "no-store"
    settings = get_or_create_settings(db)
    return serialize(settings)


@router.put("/admin/announcement", response_model=AnnouncementResponse)
def update_admin_announcement(
    payload: AnnouncementUpdate,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    settings = get_or_create_settings(db)

    cleaned_lines = [
        line.strip()
        for line in payload.content.splitlines()
        if line.strip()
    ]
    cleaned_content = "\n".join(cleaned_lines)

    settings.content = cleaned_content
    settings.is_active = bool(payload.is_active and cleaned_content)
    settings.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(settings)

    response.headers["Cache-Control"] = "no-store"
    return serialize(settings)
