"""
Script to update admin password
"""
from database import SessionLocal
from models import Admin
from auth import hash_password

def update_admin_password(email: str, new_password: str):
    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.email == email).first()
        
        if not admin:
            print(f"❌ No admin found with email: {email}")
            return
        
        # Update password
        admin.password = hash_password(new_password)
        db.commit()
        
        print(f"✅ Password updated successfully!")
        print(f"Email: {email}")
        print(f"New Password: {new_password}")
        
    except Exception as e:
        print(f"❌ Error updating password: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Update the admin password
    EMAIL = "admin1@gmail.com"
    NEW_PASSWORD = "admin123"
    
    update_admin_password(EMAIL, NEW_PASSWORD)
