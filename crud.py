
def update_product(db: Session, product_id: int, update_data):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    # Update category if provided
    if hasattr(update_data, 'category_name') and update_data.category_name:
        category = db.query(Category).filter(Category.name == update_data.category_name).first()
        if not category:
            category = Category(name=update_data.category_name)
            db.add(category)
            db.commit()
            db.refresh(category)
        product.category_id = category.id

    # Update other fields
    for field in ['name', 'description', 'price', 'quantity', 'image_pos_x', 'image_pos_y', 'image_scale']:
        value = getattr(update_data, field, None)
        if value is not None:
            setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
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
