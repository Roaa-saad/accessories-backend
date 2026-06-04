from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil, os, time, re, asyncio, uuid

from database import Base, engine, SessionLocal
from email_service import send_order_notification
from storage import upload_to_supabase, delete_from_supabase
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
from pydantic import BaseModel, EmailStr, validator
import re


# ================= APP =================
app = FastAPI()


# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://accessories-store-nu.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173"
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
try:
    Base.metadata.create_all(bind=engine)

    # Add missing columns if they don't exist
    try:
        from sqlalchemy import text

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
async def delete_image(image_id: int, db: Session = Depends(get_db)):
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
async def delete_product(product_id: int, db: Session = Depends(get_db)):
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
        
        if not admin:
            print("Admin not found")
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
def get_all_orders(db: Session = Depends(get_db)):
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
def get_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    
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
    if product.sold_out:
        raise HTTPException(400, "Product is sold out")
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


@app.post("/client/validate-discount")
def validate_discount(code: str = Form(...)):
    """Validate discount code and return discount info"""
    code_upper = code.upper().strip()
    
    discount_codes = {
        "BACKTOLUMIE": {"discount": 10, "type": "percentage"},
        "FREEGIFT": {"discount": 0, "type": "gift"}
    }
    
    if code_upper in discount_codes:
        return {
            "valid": True,
            "code": code_upper,
            **discount_codes[code_upper]
        }
    else:
        raise HTTPException(400, "Invalid discount code")


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
    cart_items: str = Form(...),  # JSON string from frontend
    db: Session = Depends(get_db)
):
    """
    Checkout endpoint - receives cart and total from frontend
    """
    
    # Parse cart_items JSON string
    import json
    try:
        items = json.loads(cart_items)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid cart_items format")
    
    # Validate cart is not empty
    if not items or len(items) == 0:
        raise HTTPException(400, "Cart is empty")
    
    # Validate customer name (letters and spaces only, no numbers/special chars)
    if not re.match(r'^[a-zA-Z\s\u0600-\u06FF]+$', customer_name):
        raise HTTPException(400, "Name can only contain letters and spaces")
    
    # Validate city (at least 2 characters)
    if not customer_city or len(customer_city.strip()) < 2:
        raise HTTPException(400, "City must be at least 2 characters long")
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, customer_email):
        raise HTTPException(400, "Invalid email format")
    
    # Validate phone number (10-15 digits, can include +, spaces, dashes)
    phone_digits = re.sub(r'[\s\-\+\(\)]', '', customer_phone)
    if not phone_digits.isdigit() or len(phone_digits) < 10 or len(phone_digits) > 15:
        raise HTTPException(400, "Phone number must be 10-15 digits")
    
    # Validate address (at least 10 characters)
    if not customer_address or len(customer_address.strip()) < 10:
        raise HTTPException(400, "Address must be at least 10 characters long")

    order = Order(
        customer_name=customer_name.strip(),
        customer_email=customer_email.lower().strip(),
        customer_city=customer_city.strip(),
        customer_phone=customer_phone.strip(),
        customer_address=customer_address.strip(),
        discount_code=discount_code.strip() if discount_code else None,
        notes=notes.strip() if notes else None,
        total_amount=total_amount  # Store frontend-calculated total
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    order_items = []
    for item in items:
        product = db.query(Product).filter(Product.id == item['product_id']).first()
        
        if not product:
            raise HTTPException(404, f"Product {item['product_id']} not found")
        if product.quantity < item['quantity']:
            raise HTTPException(400, f"Not enough stock for {product.name}")
        
        product.quantity -= item['quantity']
        product.sold_out = product.quantity == 0

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item['quantity'],
            price=item['price']  # Store the actual price paid from frontend (includes discounts)
        )
        db.add(order_item)
        
        # Store item details for email
        order_items.append({
            "product_name": product.name,
            "quantity": item['quantity'],
            "price": item['price']  # Use the price from cart (historical price paid)
        })

    db.commit()
    
    # Send email notification to admin in background (non-blocking)
    asyncio.create_task(send_order_notification({
        "order_id": order.id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "customer_city": customer_city,
        "customer_address": customer_address,
        "discount_code": discount_code,
        "notes": notes,
        "items": order_items
    }))
    
    return {"detail": "Order placed successfully", "order_id": order.id}


@app.post("/client/calculate-shipping")
def calculate_shipping(city: str = Form(...)):
    """Calculate shipping charge based on city"""
    
    city_lower = city.lower().strip()

    # Cairo & Giza
    cairo_giza = [
        'cairo', 'القاهرة',
        'giza', 'الجيزة'
    ]

    # # New Cities
    # new_cities = [
    #     'new cairo', 'القاهرة الجديدة',
    #     '6th october', '6 أكتوبر',
    #     'sheikh zayed', 'الشيخ زايد',
    #     'shorouk', 'الشروق',
    #     'obour', 'العبور',
    #     'badr', 'بدر',
    #     'new capital', 'العاصمة الإدارية',
    #     'nasr city', 'مدينة نصر',
    #     'heliopolis', 'مصر الجديدة'
    # ]

    # Delta + Canal + Alexandria
    delta_cities = [
        'alexandria', 'الإسكندرية', 'alex',
        'tanta', 'طنطا',
        'mansoura', 'المنصورة',
        'zagazig', 'الزقازيق',
        'ismailia', 'الإسماعيلية',
        'suez', 'السويس',
        'port said', 'بورسعيد',
        'damietta', 'دمياط',
        'kafr el sheikh', 'كفر الشيخ',
        'beheira', 'البحيرة',
        'gharbia', 'الغربية',
        'dakahlia', 'الدقهلية',
        'sharqia', 'الشرقية',
        'qalyubia', 'القليوبية',
        'monufia', 'المنوفية'
    ]

    # Upper Egypt + remote areas
    upper_egypt = [
        'fayoum', 'الفيوم',
        'beni suef', 'بني سويف',
        'minya', 'المنيا',
        'assiut', 'أسيوط',
        'sohag', 'سوهاج',
        'qena', 'قنا',
        'luxor', 'الأقصر',
        'aswan', 'أسوان',
        'red sea', 'البحر الأحمر',
        'matrouh', 'مطروح',
        'new valley', 'الوادي الجديد',
        'north sinai', 'شمال سيناء',
        'south sinai', 'جنوب سيناء'
    ]

    if any(c in city_lower for c in cairo_giza):
        return {"shipping_charge": 75, "city": city}

    # elif any(c in city_lower for c in new_cities):
    #     return {"shipping_charge": 75, "city": city}

    elif any(c in city_lower for c in delta_cities):
        return {"shipping_charge": 85, "city": city}

    elif any(c in city_lower for c in upper_egypt):
        return {"shipping_charge": 95, "city": city}

    else:
        return {"shipping_charge": 85, "city": city}

@app.get("/client/categories/{category_id}/products", response_model=list[dict])
def get_products_by_category(category_id: int, db: Session = Depends(get_db)):
    from models import Product
    from sqlalchemy.orm import joinedload
    products = db.query(Product).options(joinedload(Product.images), joinedload(Product.category)).filter(Product.category_id == category_id).all()
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
    db: Session = Depends(get_db)
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
                product.quantity -= item.quantity

                if product.quantity < 0:
                    product.quantity = 0

                product.sold_out = (
                    product.quantity == 0
                )

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