"""
Script to add customer_city column to orders table
Run this once after deploying the model change
"""
from database import SessionLocal
from sqlalchemy import text

def add_city_column():
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='orders' AND column_name='customer_city';
        """))
        
        if result.fetchone() is None:
            print("Adding customer_city column to orders table...")
            db.execute(text("""
                ALTER TABLE orders 
                ADD COLUMN customer_city VARCHAR;
            """))
            db.commit()
            print("✅ customer_city column added successfully!")
        else:
            print("✅ customer_city column already exists")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_city_column()
