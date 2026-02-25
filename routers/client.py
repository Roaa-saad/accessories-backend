# --- imports ---
from schemas import ProductImageResponse
from sqlalchemy.orm import joinedload
# Endpoint: Get products by category id with all images
@router.get("/categories/{category_id}/products", response_model=list[dict])
def get_products_by_category(category_id: int, db: Session = Depends(get_db)):
    from models import Product
    products = db.query(Product).options(joinedload(Product.images)).filter(Product.category_id == category_id).all()
    result = []
    for product in products:
        images = []
        if hasattr(product, 'images'):
            for img in product.images:
                images.append({
                    "id": img.id,
                    "image_url": img.image,
                    "sort_order": img.sort_order,
                    "is_cover": img.is_cover
                })
        category_obj = None
        if hasattr(product, 'category') and product.category:
            category_obj = {
                "id": product.category.id,
                "name": product.category.name
            }
        result.append({
            "id": product.id,
            "name": product.name,
            "description": getattr(product, 'description', None),
            "price": product.price,
            "discount_price": getattr(product, 'discount_price', None),
            "quantity": product.quantity,
            "sold_out": product.sold_out,
            "featured": getattr(product, 'featured', False),
            "category": category_obj,
            "image_pos_x": getattr(product, 'image_pos_x', 50),
            "image_pos_y": getattr(product, 'image_pos_y', 50),
            "image_scale": getattr(product, 'image_scale', 1),
            "images": images
        })
    return result
from models import Category

@router.get("/categories", response_model=list[str])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return [c.name for c in categories]
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
        if hasattr(product, 'category') and product.category:
            product.category_name = product.category.name
            product.category_id = product.category.id
        else:
            product.category_name = None
            product.category_id = None
    return products
