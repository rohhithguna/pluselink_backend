"""
Seed script to create initial admin user for PulseLink.
Run this after deploying to create the first admin account.

Usage:
    python seed_admin.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, init_db
from models import User, UserRole
from auth import get_password_hash
from datetime import datetime

def create_admin_user():
    """Create the initial admin user if it doesn't exist."""
    
    # Initialize database tables first
    init_db()
    
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.username == "admin").first()
        
        if existing_admin:
            print("⚠️  Admin user already exists!")
            print(f"   Username: {existing_admin.username}")
            print(f"   Role: {existing_admin.role.value}")
            return
        
        # Create admin user
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),  # Change this password!
            email="admin@pulselink.com",
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_approved=True,
            first_login=False,
            created_at=datetime.utcnow()
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("✅ Admin user created successfully!")
        print("=" * 40)
        print("   Username: admin")
        print("   Password: admin123")
        print("   Role: admin")
        print("=" * 40)
        print("⚠️  IMPORTANT: Change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
