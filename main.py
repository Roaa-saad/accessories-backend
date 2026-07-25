from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional
import shutil, os, time, re, asyncio, uuid
from routers.announcements import router as announcements_router
from routers.coupons import (
    get_coupon_calculation,
    router as coupons_router,
)

from database import Base, engine, SessionLocal
from storage import upload_to_supabase, delete_from_supabase

try:
    from email_service import send_order_notification
except ImportError:
    async def send_order_notification(order_data):
        print("Email service is not available; order email was skipped.")

from models import (
    Product,
    ProductImage,
    Order,
    OrderItem,
    Category,
    Admin,
    Coupon
)

from schemas import AdminLogin
from auth import verify_password, create_access_token
from auth_dependency import get_current_admin
from pydantic import BaseModel, EmailStr, validator
import re


# ================= APP =================
app = FastAPI()
app.include_router(announcements_router)
app.include_router(coupons_router)

# ================= CORS =================
default_origins = [
    "https://accessories-store-nu.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
]
configured_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Keep the known production/local origins even if Railway has an older
# ALLOWED_ORIGINS value.  This avoids an accidental CORS lockout after deploy.
allowed_origins = list(
    dict.fromkeys(origin.rstrip("/") for origin in [*default_origins, *configured_origins])
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
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
try:
    from sqlalchemy import inspect, text

    coupons_table_existed = inspect(engine).has_table("coupons")
    Base.metadata.create_all(bind=engine)

    # Preserve the two coupon codes that existed before admin coupon management.
    # They are inserted only when the coupons table is created for the first time.
    if not coupons_table_existed:
        seed_db = SessionLocal()
        try:
            seed_db.add_all([
                Coupon(
                    code="BACKTOLUMIE",
                    discount_type="percent",
                    discount_value=10,
                    min_order_amount=0,
                    is_active=True,
                ),
                Coupon(
                    code="FREEGIFT",
                    discount_type="gift",
                    discount_value=0,
                    min_order_amount=0,
                    is_active=True,
                ),
            ])
            seed_db.commit()
        except Exception as seed_error:
            seed_db.rollback()
            print(f"Note: Could not seed default coupons: {seed_error}")
        finally:
            seed_db.close()

    # Add missing columns if they don't exist
    try:
        with engine.connect() as conn:

            # ================= ORDERS =================

            # Check and add customer_city column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='orders'
                AND column_name='customer_city';
            """))

            if result.fetchone() is None:
                print("Adding customer_city column to orders table...")

                conn.execute(text("""
                    ALTER TABLE orders
                    ADD COLUMN customer_city VARCHAR;
                """))

                conn.commit()
                print("✅ customer_city column added successfully!")


            # Check and add discount_code column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='orders'
                AND column_name='discount_code';
            """))

            if result.fetchone() is None:
                print("Adding discount_code column to orders table...")

                conn.execute(text("""
                    ALTER TABLE orders
                    ADD COLUMN discount_code VARCHAR;
                """))

                conn.commit()
                print("✅ discount_code column added successfully!")


            # Check and add notes column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='orders'
                AND column_name='notes';
            """))

            if result.fetchone() is None:
                print("Adding notes column to orders table...")

                conn.execute(text("""
                    ALTER TABLE orders
                    ADD COLUMN notes VARCHAR;
                """))

                conn.commit()
                print("✅ notes column added successfully!")


            # Check and add total_amount column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='orders'
                AND column_name='total_amount';
            """))

            if result.fetchone() is None:
                print("Adding total_amount column to orders table...")

                conn.execute(text("""
                    ALTER TABLE orders
                    ADD COLUMN total_amount FLOAT;
                """))

                conn.commit()
                print("✅ total_amount column added successfully!")


            # Check and add is_cancelled column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='orders'
                AND column_name='is_cancelled';
            """))

            if result.fetchone() is None:
                print("Adding is_cancelled column to orders table...")

                conn.execute(text("""
                    ALTER TABLE orders
                    ADD COLUMN is_cancelled BOOLEAN DEFAULT FALSE;
                """))

                conn.commit()
                print("✅ is_cancelled column added successfully!")


            # Coupon and total breakdown fields for new orders.
            conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS subtotal_amount FLOAT;
            """))
            conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS discount_amount FLOAT;
            """))
            conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS shipping_amount FLOAT;
            """))
            conn.execute(text("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS checkout_token VARCHAR(64);
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_checkout_token
                ON orders (checkout_token)
                WHERE checkout_token IS NOT NULL;
            """))
            conn.commit()

            # ================= PRODUCTS =================

            # Check and add hidden column
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='products'
                AND column_name='hidden';
            """))

            if result.fetchone() is None:
                print("Adding hidden column to products table...")

                conn.execute(text("""
                    ALTER TABLE products
                    ADD COLUMN hidden BOOLEAN DEFAULT FALSE;
                """))

                conn.commit()
                print("✅ hidden column added successfully!")

            # Products created before the hidden column may contain NULL.
            # Preserve the original visible behaviour for those legacy rows.
            conn.execute(text("""
                UPDATE products
                SET hidden = FALSE
                WHERE hidden IS NULL;
            """))
            conn.commit()

    except Exception as e:
        print(f"Note: Could not add columns: {e}")

except Exception as e:
    print(f"Warning: Could not create database tables: {e}")
    print("This may be expected if the database is not available during startup.")


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
def clear_uploads(_admin_email: str = Depends(get_current_admin)):
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
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
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
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    try:
        print(f"Adding product: {name}")
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
            # Clean filename - remove invalid characters
            clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', image.filename)
            filename = f"{int(time.time()*1000)}_{clean_name}"
            
            try:
                    # Upload to Cloudinary
                    from storage import upload_to_cloudinary
                    image_url = await upload_to_cloudinary(image, filename)
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=500, 
                        detail=f"Failed to upload image to Cloudinary: {str(e)}. Please ensure CLOUDINARY credentials are set in Railway environment variables."
                )

            db.add(ProductImage(
                image=image_url,  # Store full URL instead of filename
                product_id=product.id,
                sort_order=index,
                is_cover=index == 0
            ))

        db.commit()
        print(f"Product created successfully: {product.id}")
        return {"detail": "Product created successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding product: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")

# -------- UPDATE PRODUCT --------
class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    hidden: Optional[bool] = None
    discount_price: Optional[float] = None
    quantity: Optional[int] = None
    featured: Optional[bool] = None 
    image_pos_x: Optional[int] = None
    image_pos_y: Optional[int] = None
    image_scale: Optional[float] = None
    category_name: Optional[str] = None



@app.put("/admin/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    update_data = data.dict(exclude_unset=True)
    category_name = update_data.pop("category_name", None)

    for field, value in update_data.items():
        setattr(product, field, value)

    if category_name is not None and category_name.strip():
        category = db.query(Category).filter(
            Category.name == category_name.strip()
        ).first()
        if not category:
            category = Category(name=category_name.strip())
            db.add(category)
            db.flush()
        product.category_id = category.id

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
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
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
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    # Clean filename - remove invalid characters
    clean_name = re.sub(r'[^a-zA-Z0-9._-]', '_', image.filename)
    filename = f"{int(time.time()*1000)}_{clean_name}"
    
    # Upload to Supabase Storage
    image_url = await upload_to_supabase(image, filename)

    db.add(ProductImage(
        image=image_url,  # Store full URL
        product_id=product.id,
        sort_order=len(product.images),
        is_cover=False
    ))

    db.commit()
    return {"detail": "Image added successfully"}


# -------- DELETE IMAGE --------
@app.delete("/admin/images/{image_id}")
async def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    img = db.query(ProductImage).filter(ProductImage.id == image_id).first()
    if not img:
        raise HTTPException(404, "Image not found")

    # Delete from Supabase Storage
    try:
        if 'supabase.co' in img.image:
            filename = img.image.split('/')[-1]
            await delete_from_supabase(filename)
    except Exception as e:
        print(f"Error deleting image from Supabase: {e}")
        # Continue even if image deletion fails

    db.delete(img)
    db.commit()
    return {"detail": "Image deleted successfully"}


# -------- DELETE PRODUCT --------
@app.delete("/admin/delete/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    # Check if product is in any orders
    order_items = db.query(OrderItem).filter(OrderItem.product_id == product_id).all()
    if order_items:
        raise HTTPException(
            400, 
            f"Cannot delete product. It is referenced in {len(order_items)} order(s). Please delete those orders first or contact support."
        )

    # Delete images from Supabase Storage
    for img in product.images:
        try:
            # Extract filename from Supabase URL
            if 'supabase.co' in img.image:
                filename = img.image.split('/')[-1]
                await delete_from_supabase(filename)
        except Exception as e:
            print(f"Error deleting image from Supabase: {e}")
            # Continue even if image deletion fails

    db.delete(product)
    db.commit()
    return {"detail": "Product deleted successfully"}


# -------- ADMIN LOGIN --------
@app.post("/admin/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    try:
        print(f"Login attempt for email: {data.email}")
        admin = db.query(Admin).filter(Admin.email == data.email).first()
        print(f"Admin found: {admin is not None}")
        
        if not admin or not admin.is_active:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        password_valid = verify_password(data.password, admin.password)
        print(f"Password valid: {password_valid}")
        
        if not password_valid:
            print("Invalid password")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"sub": admin.email})
        print("Login successful")
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during login: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




@app.get("/admin/orders")
def get_all_orders(
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    orders = db.query(Order).order_by(Order.id.desc()).all()

    response = []

    for order in orders:
        response.append({
            "order_id": order.id,
            "customer_name": order.customer_name,
            "customer_email": order.customer_email,
            "customer_city": order.customer_city,
            "customer_phone": order.customer_phone,
            "customer_address": order.customer_address,
            "discount_code": order.discount_code,
            "notes": order.notes,
            "subtotal_amount": order.subtotal_amount,
            "discount_amount": order.discount_amount,
            "shipping_amount": order.shipping_amount,
            "total_amount": order.total_amount,
            "is_delivered": order.is_delivered,
            "is_cancelled": order.is_cancelled,
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
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
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


@app.delete("/admin/orders/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    """Permanently delete an order and its rows without changing product stock."""
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()

    return {
        "detail": "Order deleted permanently",
        "order_id": order_id,
    }


# =================================================
# ================= CLIENT ========================
# =================================================

# -------- GET CATEGORIES --------
@app.get("/client/categories")
def get_categories(db: Session = Depends(get_db)):
    return [
        {"id": category.id, "name": category.name}
        for category in db.query(Category).order_by(Category.name.asc()).all()
    ]


@app.get("/client/products")
def get_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).filter(
        or_(Product.hidden.is_(False), Product.hidden.is_(None))
    ).all()
    
    # Get base URL dynamically from request
    base_url = str(request.base_url).rstrip('/')

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
            "hidden": p.hidden,
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
                    "image_url": img.image,  # Already a full URL from Supabase
                    "sort_order": img.sort_order,
                    "is_cover": img.is_cover
                }
                for img in p.images
            ]
        }
        for p in products
    ]



# ================= CART (localStorage-based, frontend manages cart) =================
# Backend validates products when adding to cart

@app.post("/client/cart/add")
def add_to_cart(
    product_id: int = Form(...),
    quantity: int = Form(...),
    db: Session = Depends(get_db)
):
    """Validate product and return product details for localStorage"""
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(404, "Product not found")
    if quantity <= 0:
        raise HTTPException(400, "Product quantity must be greater than 0")
    if product.sold_out or product.hidden:
        raise HTTPException(400, "Product is unavailable")
    if quantity > product.quantity:
        raise HTTPException(400, "Not enough stock")

    return {
        "detail": "Product validated",
        "product": {
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "discount_price": product.discount_price,
            "quantity": quantity,
            "images": [img.image for img in product.images]
        }
    }


def get_shipping_charge_for_city(city: str) -> float:
    city_lower = (city or "").lower().strip()

    cairo_giza = [
        "cairo", "القاهرة", "giza", "الجيزة",
        "6th october", "sheikh zayed", "new cairo", "shorouk",
        "obour", "badr", "new capital",
    ]
    delta_cities = [
        "alexandria", "الإسكندرية", "alex", "tanta", "طنطا",
        "mansoura", "المنصورة", "zagazig", "الزقازيق",
        "ismailia", "الإسماعيلية", "suez", "السويس",
        "port said", "بورسعيد", "damietta", "دمياط",
        "kafr el sheikh", "كفر الشيخ", "beheira", "البحيرة",
        "gharbia", "الغربية", "dakahlia", "الدقهلية",
        "sharqia", "الشرقية", "qalyubia", "القليوبية",
        "monufia", "المنوفية",
    ]
    upper_egypt = [
        "fayoum", "الفيوم", "beni suef", "بني سويف",
        "minya", "المنيا", "assiut", "أسيوط", "sohag", "سوهاج",
        "qena", "قنا",
    ]
    hurghada = ["hurghada", "الغردقة"]
    aswan = ["aswan", "أسوان"]
    matrouh = ["matrouh", "مطروح", "marsa matrouh", "مرسى مطروح"]
    north_coast = ["north coast", "الساحل الشمالي"]
    new_valley = ["new valley", "الوادي الجديد"]
    remote_145 = [
        "red sea", "البحر الأحمر", "sharm el sheikh", "شرم الشيخ",
        "arish", "العريش", "el arish", "north sinai", "شمال سيناء",
        "south sinai", "جنوب سيناء",
    ]

    if any(value in city_lower for value in cairo_giza):
        return 75
    if any(value in city_lower for value in delta_cities):
        return 85
    if any(value in city_lower for value in upper_egypt):
        return 95
    if any(value in city_lower for value in hurghada):
        return 125
    if any(value in city_lower for value in aswan):
        return 125
    if any(value in city_lower for value in matrouh):
        return 130
    if any(value in city_lower for value in north_coast):
        return 135
    if any(value in city_lower for value in new_valley):
        return 135
    if any(value in city_lower for value in remote_145):
        return 145
    return 85


@app.post("/client/checkout")
async def checkout(
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(...),
    customer_address: str = Form(...),
    customer_city: str = Form(...),
    discount_code: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    total_amount: float = Form(...),
    cart_items: str = Form(...),
    checkout_token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Create an order and calculate coupon totals using database values."""
    import json

    try:
        items = json.loads(cart_items)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid cart_items format")

    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Cart is empty")

    normalized_checkout_token = (checkout_token or "").strip() or None
    if normalized_checkout_token and (
        len(normalized_checkout_token) > 64
        or not re.match(r"^[A-Za-z0-9_-]+$", normalized_checkout_token)
    ):
        raise HTTPException(400, "Invalid checkout token")

    # Return the already-created order when the browser retries the same checkout.
    if normalized_checkout_token:
        existing_order = db.query(Order).filter(
            Order.checkout_token == normalized_checkout_token
        ).first()
        if existing_order:
            return {
                "detail": "Order placed successfully",
                "order_id": existing_order.id,
                "subtotal_amount": float(existing_order.subtotal_amount or 0),
                "discount_amount": float(existing_order.discount_amount or 0),
                "shipping_amount": float(existing_order.shipping_amount or 0),
                "total_amount": float(existing_order.total_amount or 0),
                "duplicate_prevented": True,
            }

    if not re.match(r"^[a-zA-Z\s\u0600-\u06FF]+$", customer_name):
        raise HTTPException(400, "Name can only contain letters and spaces")

    if not customer_city or len(customer_city.strip()) < 2:
        raise HTTPException(400, "City must be at least 2 characters long")

    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, customer_email):
        raise HTTPException(400, "Invalid email format")

    phone_digits = re.sub(r"[\s\-\+\(\)]", "", customer_phone)
    if not phone_digits.isdigit() or not 10 <= len(phone_digits) <= 15:
        raise HTTPException(400, "Phone number must be 10-15 digits")

    if not customer_address or len(customer_address.strip()) < 10:
        raise HTTPException(400, "Address must be at least 10 characters long")

    prepared_items = []
    subtotal = 0.0

    # Merge duplicate product rows before stock validation. This preserves the
    # same cart behaviour while preventing the same stock from being counted twice.
    merged_items = {}
    try:
        for item in items:
            product_id = int(item.get("product_id"))
            quantity = int(item.get("quantity", 0))
            if quantity <= 0:
                raise HTTPException(400, "Product quantity must be greater than 0")
            merged_items[product_id] = merged_items.get(product_id, 0) + quantity
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(400, "Invalid cart item")

    if not merged_items:
        raise HTTPException(400, "Order must contain at least one product")

    try:
        for product_id, quantity in merged_items.items():
            product = db.query(Product).filter(Product.id == product_id).with_for_update().first()

            # A simultaneous retry may have been waiting for this stock lock.
            # Re-check the token after the lock so the retry returns the first
            # order even when that order consumed the last available item.
            if normalized_checkout_token:
                existing_order = db.query(Order).filter(
                    Order.checkout_token == normalized_checkout_token
                ).first()
                if existing_order:
                    db.rollback()
                    return {
                        "detail": "Order placed successfully",
                        "order_id": existing_order.id,
                        "subtotal_amount": float(existing_order.subtotal_amount or 0),
                        "discount_amount": float(existing_order.discount_amount or 0),
                        "shipping_amount": float(existing_order.shipping_amount or 0),
                        "total_amount": float(existing_order.total_amount or 0),
                        "duplicate_prevented": True,
                    }

            if not product:
                raise HTTPException(404, f"Product {product_id} not found")
            if product.hidden or product.sold_out:
                raise HTTPException(400, f"Product {product.name} is unavailable")
            if product.quantity < quantity:
                raise HTTPException(400, f"Not enough stock for {product.name}")

            unit_price = (
                float(product.discount_price)
                if product.discount_price is not None and product.discount_price > 0
                else float(product.price)
            )
            subtotal += unit_price * quantity
            prepared_items.append((product, quantity, unit_price))

        subtotal = round(subtotal, 2)
        coupon_result = get_coupon_calculation(
            db,
            discount_code,
            subtotal,
            raise_if_invalid=bool((discount_code or "").strip()),
        )
        discount_amount = round(float(coupon_result["discount_amount"]), 2)
        subtotal_after_discount = round(subtotal - discount_amount, 2)

        base_shipping = get_shipping_charge_for_city(customer_city)
        shipping_amount = 0 if subtotal_after_discount >= 900 else base_shipping
        calculated_total = round(subtotal_after_discount + shipping_amount, 2)

        order = Order(
            customer_name=customer_name.strip(),
            customer_email=customer_email.lower().strip(),
            customer_city=customer_city.strip(),
            customer_phone=customer_phone.strip(),
            customer_address=customer_address.strip(),
            discount_code=coupon_result["code"] or None,
            notes=notes.strip() if notes else None,
            subtotal_amount=subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            total_amount=calculated_total,
            checkout_token=normalized_checkout_token,
        )
        db.add(order)
        db.flush()

        email_items = []
        for product, quantity, unit_price in prepared_items:
            product.quantity -= quantity
            product.sold_out = product.quantity == 0

            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price=unit_price,
                )
            )
            email_items.append(
                {
                    "product_name": product.name,
                    "quantity": quantity,
                    "price": unit_price,
                }
            )

        db.flush()
        saved_item_count = db.query(OrderItem).filter(
            OrderItem.order_id == order.id
        ).count()
        if saved_item_count <= 0:
            raise HTTPException(400, "Order must contain at least one product")

        coupon = coupon_result.get("coupon")
        if coupon is not None:
            coupon.times_used = int(coupon.times_used or 0) + 1

        db.commit()
        db.refresh(order)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        if normalized_checkout_token:
            existing_order = db.query(Order).filter(
                Order.checkout_token == normalized_checkout_token
            ).first()
            if existing_order:
                return {
                    "detail": "Order placed successfully",
                    "order_id": existing_order.id,
                    "subtotal_amount": float(existing_order.subtotal_amount or 0),
                    "discount_amount": float(existing_order.discount_amount or 0),
                    "shipping_amount": float(existing_order.shipping_amount or 0),
                    "total_amount": float(existing_order.total_amount or 0),
                    "duplicate_prevented": True,
                }
        raise HTTPException(409, "Duplicate order request")
    except Exception as error:
        db.rollback()
        raise HTTPException(500, f"Failed to create order: {error}")

    asyncio.create_task(
        send_order_notification(
            {
                "order_id": order.id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone,
                "customer_city": customer_city,
                "customer_address": customer_address,
                "discount_code": coupon_result["code"] or None,
                "discount_amount": discount_amount,
                "shipping_amount": shipping_amount,
                "total_amount": calculated_total,
                "notes": notes,
                "items": email_items,
            }
        )
    )

    return {
        "detail": "Order placed successfully",
        "order_id": order.id,
        "subtotal_amount": subtotal,
        "discount_amount": discount_amount,
        "shipping_amount": shipping_amount,
        "total_amount": calculated_total,
    }


@app.post("/client/calculate-shipping")
def calculate_shipping(city: str = Form(...)):
    return {
        "shipping_charge": get_shipping_charge_for_city(city),
        "city": city,
    }


@app.get("/client/categories/{category_id}/products", response_model=list[dict])
def get_products_by_category(category_id: int, db: Session = Depends(get_db)):
    from models import Product
    from sqlalchemy.orm import joinedload
    products = db.query(Product).options(
        joinedload(Product.images),
        joinedload(Product.category),
    ).filter(
        Product.category_id == category_id,
        or_(Product.hidden.is_(False), Product.hidden.is_(None)),
    ).all()
    result = []
    for product in products:
        images = []
        for img in getattr(product, 'images', []):
            images.append({
                "id": img.id,
                "image_url": img.image,
                "sort_order": img.sort_order,
                "is_cover": img.is_cover
            })
        category_obj = None
        if getattr(product, 'category', None):
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
            "hidden": getattr(product, 'hidden', False),
            "category": category_obj,
            "image_pos_x": getattr(product, 'image_pos_x', 50),
            "image_pos_y": getattr(product, 'image_pos_y', 50),
            "image_scale": getattr(product, 'image_scale', 1),
            "images": images
        })
    return result

@app.put("/admin/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    _admin_email: str = Depends(get_current_admin),
):
    order = db.query(Order).filter(
        Order.id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # لو متكنسل بالفعل -> Restore
    if order.is_cancelled:

        for item in order.items:
            product = db.query(Product).filter(
                Product.id == item.product_id
            ).first()

            if product:
                if product.quantity < item.quantity:
                    db.rollback()
                    raise HTTPException(
                        status_code=400,
                        detail=f"Not enough stock to restore order for {product.name}",
                    )
                product.quantity -= item.quantity
                product.sold_out = product.quantity == 0

        order.is_cancelled = False

        db.commit()
        db.refresh(order)

        return {
            "detail": "Order restored successfully",
            "order_id": order.id,
            "is_cancelled": False
        }

    # لو Pending -> Cancel
    for item in order.items:
        product = db.query(Product).filter(
            Product.id == item.product_id
        ).first()

        if product:
            product.quantity += item.quantity
            product.sold_out = False

    order.is_cancelled = True
    order.is_delivered = False

    db.commit()
    db.refresh(order)

    return {
        "detail": "Order cancelled successfully",
        "order_id": order.id,
        "is_cancelled": True
    }