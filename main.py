from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil, os, time

from database import Base, engine, SessionLocal
from models import (
    Product,
    ProductImage,
    Order,
    OrderItem,
    Category,
    Admin
)

from schemas import AdminLogin
from auth import verify_password, create_access_token
from pydantic import BaseModel


# ================= APP =================
app = FastAPI()


# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= STATIC FILES =================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def clear_uploads_folder(folder_path=UPLOAD_DIR):
    if not os.path.exists(folder_path):
        return 0

    deleted_files = 0
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
            deleted_files += 1

    return deleted_files



# ================= DATABASE =================
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =================================================
# ================= ADMIN =========================
# =================================================


@app.delete("/admin/clear-uploads")
def clear_uploads():
    deleted_count = clear_uploads_folder()
    return {
        "detail": "Uploads folder cleared successfully",
        "deleted_files": deleted_count
    }


# -------- ADD CATEGORY --------
class CategoryCreate(BaseModel):
    name: str


@app.post("/admin/categories")
def add_category(
    data: CategoryCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Category).filter(Category.name == data.name).first()
    if existing:
        raise HTTPException(400, "Category already exists")

    category = Category(name=data.name)
    db.add(category)
    db.commit()
    db.refresh(category)

    return {
        "id": category.id,
        "name": category.name
    }


# -------- ADD PRODUCT --------
@app.post("/admin/add")
async def add_product(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    price: float = Form(...),
    discount_price: Optional[float] = Form(None),
    quantity: int = Form(...),
    category_name: str = Form(...),
    images: List[UploadFile] = File(...),
    featured: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(Category.name == category_name).first()
    if not category:
        category = Category(name=category_name)
        db.add(category)
        db.commit()
        db.refresh(category)

    product = Product(
        name=name,
        description=description,
        price=price,
        discount_price=discount_price,
        quantity=quantity,
        sold_out=quantity == 0,
        category_id=category.id,
        featured=featured, 
        image_pos_x=50,
        image_pos_y=50,
        image_scale=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    for index, image in enumerate(images):
        filename = f"{int(time.time()*1000)}_{image.filename}"
        path = os.path.join(UPLOAD_DIR, filename)

        with open(path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        db.add(ProductImage(
            image=filename,
            product_id=product.id,
            sort_order=index,
            is_cover=index == 0
        ))

    db.commit()
    return {"detail": "Product created successfully"}

# -------- UPDATE PRODUCT --------
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    quantity: Optional[int] = None
    featured: Optional[bool] = None 
    image_pos_x: Optional[int] = None
    image_pos_y: Optional[int] = None
    image_scale: Optional[float] = None



@app.put("/admin/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(product, field, value)

    product.sold_out = product.quantity == 0
    db.commit()
    db.refresh(product)

    return {"detail": "Product updated successfully"}



# -------- REORDER IMAGES + SET COVER --------
class ImageOrderItem(BaseModel):
    id: int
    sort_order: int


class ImageReorderRequest(BaseModel):
    images: List[ImageOrderItem]
    cover_image_id: Optional[int] = None


@app.put("/admin/products/{product_id}/images/reorder")
def reorder_images(
    product_id: int,
    data: ImageReorderRequest,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    for img in product.images:
        img.is_cover = False

    for item in data.images:
        img = db.query(ProductImage).filter(
            ProductImage.id == item.id,
            ProductImage.product_id == product_id
        ).first()
        if img:
            img.sort_order = item.sort_order

    if data.cover_image_id:
        cover_img = db.query(ProductImage).filter(
            ProductImage.id == data.cover_image_id,
            ProductImage.product_id == product_id
        ).first()
        if cover_img:
            cover_img.is_cover = True

    if not any(img.is_cover for img in product.images):
        product.images[0].is_cover = True

    db.commit()
    return {"detail": "Images reordered & cover saved"}


# -------- ADD IMAGE --------
@app.post("/admin/products/{product_id}/images")
async def add_image(
    product_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    filename = f"{int(time.time()*1000)}_{image.filename}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    db.add(ProductImage(
        image=filename,
        product_id=product.id,
        sort_order=len(product.images),
        is_cover=False
    ))

    db.commit()
    return {"detail": "Image added successfully"}


# -------- DELETE IMAGE --------
@app.delete("/admin/images/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db)):
    img = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "Image not found")

    path = os.path.join(UPLOAD_DIR, img.image)
    if os.path.exists(path):
        os.remove(path)

    db.delete(img)
    db.commit()
    return {"detail": "Image deleted successfully"}


# -------- DELETE PRODUCT --------
@app.delete("/admin/delete/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    for img in product.images:
        path = os.path.join(UPLOAD_DIR, img.image)
        if os.path.exists(path):
            os.remove(path)

    db.delete(product)
    db.commit()
    return {"detail": "Product deleted successfully"}


# -------- ADMIN LOGIN --------
@app.post("/admin/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.email == data.email).first()
    if not admin or not verify_password(data.password, admin.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": admin.email})
    return {"access_token": token, "token_type": "bearer"}




@app.get("/admin/orders")
def get_all_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.id.desc()).all()

    response = []

    for order in orders:
        response.append({
            "order_id": order.id,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "customer_phone": order.customer_phone,
            "customer_address": order.customer_address,
            "is_delivered": order.is_delivered,
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product else "",
                    "quantity": item.quantity,
                    "price": item.price,
                    "images": [
                        img.image for img in item.product.images
                    ] if item.product else []
                }
                for item in order.items
            ]
        })

    return response

@app.put("/admin/orders/{order_id}/deliver")
def toggle_order_delivery(
    order_id: int,
    delivered: bool = Form(...),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.is_delivered = delivered
    db.commit()
    db.refresh(order)

    return {
        "detail": "Delivery status updated",
        "order_id": order.id,
        "is_delivered": order.is_delivered
    }


# =================================================
# ================= CLIENT ========================
# =================================================

# -------- GET CATEGORIES --------
@app.get("/client/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "discount_price": p.discount_price,
            "quantity": p.quantity,
            "sold_out": p.sold_out,
            "featured": p.featured,   # ⭐ الجديد
            "category": {
                "id": p.category.id,
                "name": p.category.name
            } if p.category else None,
            "image_pos_x": p.image_pos_x,
            "image_pos_y": p.image_pos_y,
            "image_scale": p.image_scale,
            "images": [
                {
                    "id": img.id,
                    "image_url": f"http://127.0.0.1:8000/uploads/{img.image}",
                    "sort_order": img.sort_order,
                    "is_cover": img.is_cover
                }
                for img in p.images
            ]
        }
        for p in products
    ]



# ================= CART =================
cart = []

@app.post("/client/cart/add")
def add_to_cart(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(404, "Product not found")
    if product.sold_out:
        raise HTTPException(400, "Product is sold out")
    if quantity > product.quantity:
        raise HTTPException(400, "Not enough stock")

    existing = next((i for i in cart if i["product_id"] == product_id), None)

    if existing:
        existing["quantity"] += quantity
    else:
        cart.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": quantity,
            "images": [img.image for img in product.images]
        })

    return {"detail": "Added to cart", "cart": cart}


@app.post("/client/checkout")
def checkout(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(...),
    customer_address: str = Form(...),
    db: Session = Depends(get_db)
):
    if not cart:
        raise HTTPException(400, "Cart is empty")

    order = Order(
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        customer_address=customer_address
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    for item in cart:
        product = db.query(Product).filter(Product.id == item["product_id"]).first()
        product.quantity -= item["quantity"]
        product.sold_out = product.quantity == 0

        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item["quantity"],
            price=product.price
        ))

    db.commit()
    cart.clear()
    return {"detail": "Order placed successfully"}


@app.get("/client/cart")
def get_cart():
    return cart


@app.delete("/client/cart/remove/{product_id}")
def remove_from_cart(product_id: int):
    global cart
    cart = [item for item in cart if item["product_id"] != product_id]
    return {"detail": "Item removed from cart", "cart": cart}

@app.get("/client/categories/{category_id}/products")
def get_products_by_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    products = (
        db.query(Product)
        .filter(Product.category_id == category_id)
        .all()
    )

    return products
