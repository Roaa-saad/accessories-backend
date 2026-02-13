"""
Script to fix admins table - add is_active column if missing
"""
from database import SessionLocal, engine
from sqlalchemy import text

def fix_admins_table():
    db = SessionLocal()
    try:
        # Check if is_active column exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='admins' AND column_name='is_active';
        """))
        
        if result.fetchone() is None:
            print("Adding is_active column to admins table...")
            db.execute(text("""
                ALTER TABLE admins 
                ADD COLUMN is_active BOOLEAN DEFAULT true;
            """))
            db.commit()
            print("✅ is_active column added successfully!")
        else:
            print("✅ is_active column already exists")
            
        # Update any NULL values to true
        db.execute(text("""
            UPDATE admins 
            SET is_active = true 
            WHERE is_active IS NULL;
        """))
        db.commit()
        print("✅ Updated NULL values to true")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_admins_table()
