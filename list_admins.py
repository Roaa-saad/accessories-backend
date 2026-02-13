"""
Script to list all admin users in the database
"""
from database import SessionLocal
from models import Admin

def list_admins():
    db = SessionLocal()
    try:
        admins = db.query(Admin).all()
        
        if not admins:
            print("No admin users found in database.")
            return
        
        print(f"Found {len(admins)} admin user(s):")
        print("-" * 60)
        for admin in admins:
            print(f"ID: {admin.id}")
            print(f"Email: {admin.email}")
            print(f"Password Hash: {admin.password[:50]}...")
            print(f"Active: {admin.is_active}")
            print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error listing admins: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_admins()
