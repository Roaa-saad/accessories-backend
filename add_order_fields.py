"""
Migration script to add discount_code and notes columns to orders table
Run this once locally or let main.py auto-migrate on Railway
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='orders' 
            AND column_name IN ('discount_code', 'notes')
        """))
        
        existing_columns = [row[0] for row in result]
        
        # Add discount_code if not exists
        if 'discount_code' not in existing_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN discount_code VARCHAR"))
            conn.commit()
            print("✅ Added discount_code column")
        else:
            print("ℹ️  discount_code column already exists")
        
        # Add notes if not exists
        if 'notes' not in existing_columns:
            conn.execute(text("ALTER TABLE orders ADD COLUMN notes VARCHAR"))
            conn.commit()
            print("✅ Added notes column")
        else:
            print("ℹ️  notes column already exists")
    
    print("✅ Migration completed successfully!")
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
