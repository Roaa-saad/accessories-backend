"""
Reset admin password - creates new admin if doesn't exist
"""
from database import SessionLocal
from models import Admin
from auth import hash_password
from sqlalchemy import text

def reset_admin():
    db = SessionLocal()
    try:
        # Delete existing admin and create fresh one
        db.execute(text("DELETE FROM admins WHERE email = 'admin@store.com'"))
        db.commit()
        
        # Create new admin
        new_password = "admin123"
        hashed = hash_password(new_password)
        
        new_admin = Admin(
            email="admin@store.com",
            password=hashed,
            is_active=True
        )
        
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        
        print("✅ Admin account created successfully!")
        print(f"Email: admin@store.com")
        print(f"Password: {new_password}")
        print(f"Hashed password: {hashed[:50]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_admin()
