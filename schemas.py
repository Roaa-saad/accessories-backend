from pydantic import BaseModel

class ProductBase(BaseModel):
    name: str
    price: float
    quantity: int
    category_name: str



class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int
    image_url: str | None
    sold_out: bool
    category_id: int | None

    class Config:
        from_attributes = True

from pydantic import BaseModel, EmailStr


from typing import Optional, List


class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AdminResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

from pydantic import BaseModel, EmailStr
from typing import Optional, List


# ================= ADMIN =================
class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ================= PRODUCT =================
class ProductUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    price: Optional[float]
    quantity: Optional[int]
    image_pos_x: Optional[int]
    image_pos_y: Optional[int]
    image_scale: Optional[float]
    category_name: Optional[str]


class ImageReorderItem(BaseModel):
    id: int
    order: int


class ImageReorderRequest(BaseModel):
    images: List[ImageReorderItem]
    cover_image_id: Optional[int] = None

class CategoryCreate(BaseModel):
    name: str


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
