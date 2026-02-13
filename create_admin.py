"""
Script to create an admin user in the database
Run this script after setting up your database
"""
from database import SessionLocal
from models import Admin
from auth import hash_password

def create_admin(email: str, password: str):
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing_admin = db.query(Admin).filter(Admin.email == email).first()
        if existing_admin:
            print(f"Admin with email {email} already exists!")
            return
        
        # Create new admin with hashed password
        hashed_password = hash_password(password)
        new_admin = Admin(
            email=email,
            password=hashed_password
        )
        
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        
        print(f"✅ Admin created successfully!")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Hashed: {hashed_password[:50]}...")
        
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Change these values to your desired admin credentials
    ADMIN_EMAIL = "admin@accessories.com"
    ADMIN_PASSWORD = "admin123"
    
    create_admin(ADMIN_EMAIL, ADMIN_PASSWORD)
