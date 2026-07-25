from datetime import datetime, timezone
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth_dependency import get_current_admin
from database import SessionLocal
from models import Coupon


router = APIRouter(tags=["Coupons"])

ALLOWED_DISCOUNT_TYPES = {"percent", "fixed", "gift"}
CODE_PATTERN = re.compile(r"^[A-Z0-9_-]+$")


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    discount_type: str = Field(..., min_length=4, max_length=20)
    discount_value: float = 0
    min_order_amount: float = 0
    usage_limit: Optional[int] = None
    is_active: bool = True
    expires_at: Optional[datetime] = None


class CouponUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=50)
    discount_type: Optional[str] = Field(default=None, min_length=4, max_length=20)
    discount_value: Optional[float] = None
    min_order_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class CouponValidationRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    subtotal: float = Field(..., ge=0)


class CouponResponse(BaseModel):
    id: int
    code: str
    discount_type: str
    discount_value: float
    min_order_amount: float
    usage_limit: Optional[int]
    times_used: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class CouponListResponse(BaseModel):
    coupons: List[CouponResponse]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_code(code: str) -> str:
    normalized = (code or "").strip().upper()
    if not normalized or not CODE_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon code can only contain letters, numbers, - and _",
        )
    return normalized


def normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def validate_coupon_fields(
    discount_type: str,
    discount_value: float,
    min_order_amount: float,
    usage_limit: Optional[int],
) -> tuple[str, float, float, Optional[int]]:
    normalized_type = (discount_type or "").strip().lower()
    if normalized_type not in ALLOWED_DISCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Discount type must be percent, fixed, or gift",
        )

    value = float(discount_value or 0)
    minimum = float(min_order_amount or 0)

    if minimum < 0:
        raise HTTPException(400, "Minimum order amount cannot be negative")

    if usage_limit is not None and usage_limit < 1:
        raise HTTPException(400, "Usage limit must be at least 1")

    if normalized_type == "percent":
        if value <= 0 or value > 100:
            raise HTTPException(400, "Percentage discount must be between 0 and 100")
    elif normalized_type == "fixed":
        if value <= 0:
            raise HTTPException(400, "Fixed discount must be greater than 0")
    else:
        value = 0

    return normalized_type, value, minimum, usage_limit


def serialize_coupon(coupon: Coupon) -> dict:
    return {
        "id": coupon.id,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value or 0),
        "min_order_amount": float(coupon.min_order_amount or 0),
        "usage_limit": coupon.usage_limit,
        "times_used": int(coupon.times_used or 0),
        "is_active": bool(coupon.is_active),
        "expires_at": coupon.expires_at,
        "created_at": coupon.created_at,
        "updated_at": coupon.updated_at,
    }


def get_coupon_calculation(
    db: Session,
    code: Optional[str],
    subtotal: float,
    *,
    raise_if_invalid: bool = True,
) -> dict:
    normalized_code = (code or "").strip().upper()
    subtotal_value = max(float(subtotal or 0), 0)

    if not normalized_code:
        return {
            "valid": False,
            "coupon": None,
            "code": "",
            "discount_type": None,
            "discount_value": 0,
            "discount_amount": 0,
            "subtotal_after_discount": subtotal_value,
            "message": "",
        }

    coupon = db.query(Coupon).filter(Coupon.code == normalized_code).first()

    detail = None
    now = datetime.utcnow()

    if coupon is None:
        detail = "Invalid coupon code"
    elif not coupon.is_active:
        detail = "This coupon is currently inactive"
    elif coupon.expires_at and coupon.expires_at < now:
        detail = "This coupon has expired"
    elif coupon.usage_limit is not None and int(coupon.times_used or 0) >= coupon.usage_limit:
        detail = "This coupon has reached its usage limit"
    elif subtotal_value < float(coupon.min_order_amount or 0):
        detail = (
            f"Minimum order amount for this coupon is "
            f"{float(coupon.min_order_amount):.2f} EGP"
        )

    if detail:
        if raise_if_invalid:
            raise HTTPException(status_code=400, detail=detail)
        return {
            "valid": False,
            "coupon": coupon,
            "code": normalized_code,
            "discount_type": coupon.discount_type if coupon else None,
            "discount_value": float(coupon.discount_value or 0) if coupon else 0,
            "discount_amount": 0,
            "subtotal_after_discount": subtotal_value,
            "message": detail,
        }

    if coupon.discount_type == "percent":
        discount_amount = subtotal_value * (float(coupon.discount_value) / 100)
        message = f"{float(coupon.discount_value):g}% discount applied"
    elif coupon.discount_type == "fixed":
        discount_amount = min(float(coupon.discount_value), subtotal_value)
        message = f"{float(coupon.discount_value):g} EGP discount applied"
    else:
        discount_amount = 0
        message = "Coupon applied. A free gift will be added to your order"

    discount_amount = round(max(discount_amount, 0), 2)
    subtotal_after_discount = round(max(subtotal_value - discount_amount, 0), 2)

    return {
        "valid": True,
        "coupon": coupon,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": float(coupon.discount_value or 0),
        "discount_amount": discount_amount,
        "subtotal_after_discount": subtotal_after_discount,
        "message": message,
    }


@router.get("/admin/coupons", response_model=CouponListResponse)
def get_admin_coupons(
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    coupons = db.query(Coupon).order_by(Coupon.id.desc()).all()
    return {"coupons": [serialize_coupon(coupon) for coupon in coupons]}


@router.post(
    "/admin/coupons",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    code = normalize_code(payload.code)

    existing = db.query(Coupon).filter(Coupon.code == code).first()
    if existing:
        raise HTTPException(400, "Coupon code already exists")

    discount_type, discount_value, minimum, usage_limit = validate_coupon_fields(
        payload.discount_type,
        payload.discount_value,
        payload.min_order_amount,
        payload.usage_limit,
    )

    coupon = Coupon(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        min_order_amount=minimum,
        usage_limit=usage_limit,
        times_used=0,
        is_active=payload.is_active,
        expires_at=normalize_datetime(payload.expires_at),
    )

    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return serialize_coupon(coupon)


@router.put("/admin/coupons/{coupon_id}", response_model=CouponResponse)
def update_admin_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Coupon not found")

    next_code = normalize_code(payload.code) if payload.code is not None else coupon.code
    duplicate = db.query(Coupon).filter(
        Coupon.code == next_code,
        Coupon.id != coupon_id,
    ).first()
    if duplicate:
        raise HTTPException(400, "Coupon code already exists")

    next_type = payload.discount_type if payload.discount_type is not None else coupon.discount_type
    next_value = payload.discount_value if payload.discount_value is not None else coupon.discount_value
    next_minimum = (
        payload.min_order_amount
        if payload.min_order_amount is not None
        else coupon.min_order_amount
    )
    next_limit = payload.usage_limit
    if "usage_limit" not in payload.model_fields_set:
        next_limit = coupon.usage_limit

    discount_type, discount_value, minimum, usage_limit = validate_coupon_fields(
        next_type,
        next_value,
        next_minimum,
        next_limit,
    )

    coupon.code = next_code
    coupon.discount_type = discount_type
    coupon.discount_value = discount_value
    coupon.min_order_amount = minimum
    coupon.usage_limit = usage_limit

    if payload.is_active is not None:
        coupon.is_active = payload.is_active

    if "expires_at" in payload.model_fields_set:
        coupon.expires_at = normalize_datetime(payload.expires_at)

    coupon.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(coupon)
    return serialize_coupon(coupon)


@router.patch("/admin/coupons/{coupon_id}/toggle", response_model=CouponResponse)
def toggle_admin_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Coupon not found")

    coupon.is_active = not coupon.is_active
    coupon.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(coupon)
    return serialize_coupon(coupon)


@router.delete("/admin/coupons/{coupon_id}")
def delete_admin_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Coupon not found")

    db.delete(coupon)
    db.commit()
    return {"detail": "Coupon deleted successfully"}


@router.post("/client/validate-coupon")
def validate_public_coupon(
    payload: CouponValidationRequest,
    db: Session = Depends(get_db),
):
    result = get_coupon_calculation(db, payload.code, payload.subtotal)
    result.pop("coupon", None)
    return result


# Keep the old form endpoint working for any older frontend build.
@router.post("/client/validate-discount")
def validate_legacy_discount(
    code: str = Form(...),
    subtotal: float = Form(0),
    db: Session = Depends(get_db),
):
    result = get_coupon_calculation(db, code, subtotal)
    result.pop("coupon", None)
    return {
        **result,
        "discount": result["discount_value"],
        "type": result["discount_type"],
    }
