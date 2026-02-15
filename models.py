from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    Text
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
        cascade="all, delete"
    )


# ================= ADMIN =================
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


# ================= PRODUCT =================
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    Text
)
from sqlalchemy.orm import relationship
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    price = Column(Float, nullable=False)
    discount_price = Column(Float, nullable=True)

    quantity = Column(Integer, nullable=False)
    sold_out = Column(Boolean, default=False)

    # ⭐ FEATURED (الجديد)
    featured = Column(Boolean, default=False)

    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category", back_populates="products")

    image_pos_x = Column(Integer, default=50)
    image_pos_y = Column(Integer, default=50)
    image_scale = Column(Float, default=1)

    images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order"
    )


# ================= PRODUCT IMAGES =================
class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    image = Column(String, nullable=False)

    sort_order = Column(Integer, default=0)    # ترتيب الصورة
    is_cover = Column(Boolean, default=False)  # هل كافر؟

    product_id = Column(Integer, ForeignKey("products.id"))
    product = relationship("Product", back_populates="images")


# ================= ORDER =================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_city = Column(String, nullable=True)  # New city field
    customer_address = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)

    is_delivered = Column(Boolean, default=False)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan"
    )


# ================= ORDER ITEMS =================
class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
