
from fastapi import HTTPException

# ...existing code...

@router.put("/products/{product_id}", response_model=schemas.ProductResponse)
def update_product(product_id: int, update: schemas.ProductUpdate, db: Session = Depends(get_db)):
    product = crud.update_product(db, product_id, update)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
import crud, schemas
from database import get_db
import shutil, os

router = APIRouter(prefix="/admin")

@router.post("/products", response_model=schemas.ProductResponse)
def add_product(
    product: schemas.ProductCreate,
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_path = None
    if image:
        os.makedirs("static/images", exist_ok=True)
        image_path = f"static/images/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    return crud.create_product(db, product, image_path)

@router.delete("/products/{product_id}", response_model=schemas.ProductResponse)
def remove_product(product_id: int, db: Session = Depends(get_db)):
    return crud.delete_product(db, product_id)
