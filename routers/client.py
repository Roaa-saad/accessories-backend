from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import crud, schemas
from database import get_db

router = APIRouter(prefix="/client")

@router.get("/products", response_model=list[schemas.ProductResponse])
def list_products(db: Session = Depends(get_db)):
    products = crud.get_products(db)
    # لو فيه صورة، ممكن نضيف URL كامل للعرض في الـ frontend
    for product in products:
        if product.image:
            product.image_url = product.image
        else:
            product.image_url = None
        # Always set the current category name
        if product.category:
            product.category_name = product.category.name
        else:
            product.category_name = None
    return products
