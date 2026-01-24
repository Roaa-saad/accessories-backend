from sqlalchemy.orm import Session
from models import Product, Category


def get_products(db: Session):
    return db.query(Product).all()

def create_product(db: Session, product_data, image_path=None):
    category = db.query(Category).filter(
        Category.name == product_data.category_name
    ).first()

    if not category:
        category = Category(name=product_data.category_name)
        db.add(category)
        db.commit()
        db.refresh(category)

    product = Product(
        name=product_data.name,
        price=product_data.price,
        quantity=product_data.quantity,
        category_id=category.id,
        image=image_path,
        sold_out=product_data.quantity == 0
    )

    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def delete_product(db: Session, product_id: int):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        db.delete(product)
        db.commit()
    return product
