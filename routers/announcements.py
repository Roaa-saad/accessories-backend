from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth_dependency import get_current_admin
from database import SessionLocal
from models import Announcement, AnnouncementSetting


router = APIRouter(tags=["Announcement Bar"])
DEFAULT_CONTENT = "Free Shipping on orders over 900 EGP"


class AnnouncementCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=300)
    is_active: bool = True


class AnnouncementUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=300)
    is_active: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    id: int
    content: str
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AnnouncementListResponse(BaseModel):
    announcements: List[AnnouncementResponse]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def clean_content(content: str) -> str:
    cleaned = " ".join(content.split()).strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Announcement text cannot be empty",
        )
    return cleaned


def serialize(item: Announcement) -> dict:
    return {
        "id": item.id,
        "content": item.content,
        "is_active": bool(item.is_active),
        "sort_order": item.sort_order or 0,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def migrate_legacy_settings(db: Session) -> None:
    """Move the old single-record announcement into the new CRUD table once."""
    if db.query(Announcement.id).first() is not None:
        return

    legacy = db.query(AnnouncementSetting).filter(
        AnnouncementSetting.id == 1
    ).first()

    legacy_lines = []
    if legacy and legacy.content:
        legacy_lines = [
            line.strip()
            for line in legacy.content.splitlines()
            if line.strip()
        ]

    if not legacy_lines:
        legacy_lines = [DEFAULT_CONTENT]

    for index, line in enumerate(legacy_lines):
        db.add(
            Announcement(
                content=clean_content(line),
                is_active=bool(legacy.is_active) if legacy else True,
                sort_order=index,
            )
        )

    db.commit()


def get_all_announcements(db: Session) -> list[Announcement]:
    migrate_legacy_settings(db)
    return (
        db.query(Announcement)
        .order_by(Announcement.sort_order.asc(), Announcement.id.asc())
        .all()
    )


@router.get("/announcement", response_model=AnnouncementListResponse)
def get_public_announcements(
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

    items = [item for item in get_all_announcements(db) if item.is_active]
    return {"announcements": [serialize(item) for item in items]}


@router.get("/admin/announcements", response_model=AnnouncementListResponse)
def get_admin_announcements(
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    response.headers["Cache-Control"] = "no-store"
    items = get_all_announcements(db)
    return {"announcements": [serialize(item) for item in items]}


@router.post(
    "/admin/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_announcement(
    payload: AnnouncementCreate,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    migrate_legacy_settings(db)

    max_order = db.query(func.max(Announcement.sort_order)).scalar()
    item = Announcement(
        content=clean_content(payload.content),
        is_active=payload.is_active,
        sort_order=(max_order if max_order is not None else -1) + 1,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    response.headers["Cache-Control"] = "no-store"
    return serialize(item)


@router.put(
    "/admin/announcements/{announcement_id}",
    response_model=AnnouncementResponse,
)
def update_admin_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if payload.content is not None:
        item.content = clean_content(payload.content)

    if payload.is_active is not None:
        item.is_active = payload.is_active

    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    response.headers["Cache-Control"] = "no-store"
    return serialize(item)


@router.patch(
    "/admin/announcements/{announcement_id}/toggle",
    response_model=AnnouncementResponse,
)
def toggle_admin_announcement(
    announcement_id: int,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement not found")

    item.is_active = not item.is_active
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)

    response.headers["Cache-Control"] = "no-store"
    return serialize(item)


@router.delete("/admin/announcements/{announcement_id}")
def delete_admin_announcement(
    announcement_id: int,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Announcement not found")

    db.delete(item)
    db.commit()

    response.headers["Cache-Control"] = "no-store"
    return {"detail": "Announcement deleted successfully"}


# Backward-compatible routes for the previous single-text admin page.
class LegacyAnnouncementUpdate(BaseModel):
    content: str = Field(default="", max_length=600)
    is_active: bool = False


@router.get("/admin/announcement")
def get_legacy_admin_announcement(
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    response.headers["Cache-Control"] = "no-store"
    items = get_all_announcements(db)
    return {
        "id": 1,
        "content": "\n".join(item.content for item in items),
        "is_active": any(item.is_active for item in items),
        "updated_at": max(
            (item.updated_at for item in items if item.updated_at),
            default=None,
        ),
    }


@router.put("/admin/announcement")
def update_legacy_admin_announcement(
    payload: LegacyAnnouncementUpdate,
    response: Response,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    lines = [line.strip() for line in payload.content.splitlines() if line.strip()]

    db.query(Announcement).delete(synchronize_session=False)
    for index, line in enumerate(lines):
        db.add(
            Announcement(
                content=clean_content(line),
                is_active=bool(payload.is_active),
                sort_order=index,
            )
        )

    db.commit()
    response.headers["Cache-Control"] = "no-store"

    return {
        "id": 1,
        "content": "\n".join(lines),
        "is_active": bool(payload.is_active and lines),
        "updated_at": datetime.utcnow(),
    }
