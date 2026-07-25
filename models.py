from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


# ================= CATEGORY =================
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

    products = relationship(
        "Product",
        back_populates="category",
        cascade="all, delete",
    )


# ================= ADMIN =================
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


# ================= PRODUCT =================
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    price = Column(Float, nullable=False)
    discount_price = Column(Float, nullable=True)

    quantity = Column(Integer, nullable=False)
    sold_out = Column(Boolean, default=False)

    featured = Column(Boolean, default=False)

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
    )

    category = relationship(
        "Category",
        back_populates="products",
    )

    image_pos_x = Column(Integer, default=50)
    image_pos_y = Column(Integer, default=50)
    image_scale = Column(Float, default=1)

    images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )

    hidden = Column(Boolean, default=False)


# ================= PRODUCT IMAGES =================
class ProductImage(Base):
    __tablename__  = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    image = Column(String, nullable=False)

    sort_order = Column(Integer, default=0)
    is_cover = Column(Boolean, default=False)

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
    )

    product = relationship(
        "Product",
        back_populates="images",
    )


# ================= ORDER =================
class Order(Base):
    __tablename__  = "orders"

    id = Column(Integer, primary_key=True, index=True)

    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_city = Column(String, nullable=True)
    customer_address = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)

    discount_code = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    subtotal_amount = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    shipping_amount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)

    is_delivered = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


# ================= ORDER ITEMS =================
class OrderItem(Base):
    __tablename__  = "order_items"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(
        Integer,
        ForeignKey("orders.id"),
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
    )

    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

    order = relationship(
        "Order",
        back_populates="items",
    )

    product = relationship("Product")


# ================= ANNOUNCEMENT BAR =================
# ================= ANNOUNCEMENT BAR =================
class AnnouncementSetting(Base):
    __tablename__ = "announcement_settings"

    id = Column(
        Integer,
        primary_key=True,
        default=1,
    )

    content = Column(
        Text,
        nullable=False,
        default="Free Shipping on orders over 900 EGP",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ================= ANNOUNCEMENTS CRUD =================
class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(300), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

# ================= COUPONS =================
class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Float, nullable=False, default=0)
    min_order_amount = Column(Float, nullable=False, default=0)
    usage_limit = Column(Integer, nullable=True)
    times_used = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

