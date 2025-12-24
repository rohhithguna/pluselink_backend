"""
Database migration script for user management features.
Adds new columns to users table and creates activity_logs table.
"""
from database import SessionLocal, engine, Base
from sqlalchemy import text
from models import User, ActivityLog, ActivityType
from auth import get_password_hash
from datetime import datetime

def migrate_database():
    """Run database migration for new user management features."""
    
    db = SessionLocal()
    
    try:
        result = db.execute(text("PRAGMA table_info(users)")).fetchall()
        column_names = [row[1] for row in result]
        
        print("Current columns in users table:", column_names)
        
        new_columns = [
            ("department", "VARCHAR", "NULL"),
            ("year", "VARCHAR", "NULL"),
            ("section", "VARCHAR", "NULL"),
            ("phone", "VARCHAR", "NULL"),
            ("is_active", "BOOLEAN", "1"),
            ("first_login", "BOOLEAN", "1"),
            ("last_login_at", "DATETIME", "NULL"),
        ]
        
        for col_name, col_type, default in new_columns:
            if col_name not in column_names:
                try:
                    if default == "NULL":
                        db.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    else:
                        db.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type} DEFAULT {default}"))
                    print(f"✓ Added column: {col_name}")
                except Exception as e:
                    print(f"⚠ Column {col_name} may already exist: {e}")
        
        db.commit()
        
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    activity_type VARCHAR NOT NULL,
                    description VARCHAR NOT NULL,
                    ip_address VARCHAR,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_activity_logs_created_at ON activity_logs(created_at)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_activity_logs_user_id ON activity_logs(user_id)"))
            db.commit()
            print("✓ Created activity_logs table")
        except Exception as e:
            print(f"⚠ activity_logs table may already exist: {e}")
        
        try:
            db.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
            db.execute(text("UPDATE users SET first_login = 0 WHERE first_login IS NULL"))
            db.commit()
            print("✓ Updated existing users with default values")
        except Exception as e:
            print(f"⚠ Error updating existing users: {e}")
        
        print("\n✅ Migration completed successfully!")
        
        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        print(f"Total users in database: {user_count}")
        
    except Exception as e:
        print(f"Migration error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def seed_demo_users():
    """Seed demo users if database is empty."""
    from models import UserRole
    
    db = SessionLocal()
    
    try:
        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        
        if user_count > 0:
            print(f"Database already has {user_count} users. Skipping seed.")
            return
        
        demo_users = [
            {
                "username": "root",
                "email": "root@pulseconnect.edu",
                "password": "root123",
                "role": UserRole.SUPER_ADMIN,
                "full_name": "Root Administrator",
                "department": "IT Administration",
                "is_active": True,
                "first_login": False,
            },
            {
                "username": "superadmin",
                "email": "superadmin@pulseconnect.edu",
                "password": "admin123",
                "role": UserRole.SUPER_ADMIN,
                "full_name": "Super Administrator",
                "department": "Administration",
                "is_active": True,
                "first_login": False,
            },
            {
                "username": "collegeadmin",
                "email": "admin@pulseconnect.edu",
                "password": "admin123",
                "role": UserRole.COLLEGE_ADMIN,
                "full_name": "College Administrator",
                "department": "College Administration",
                "is_active": True,
                "first_login": False,
            },
            {
                "username": "faculty",
                "email": "faculty@pulseconnect.edu",
                "password": "faculty123",
                "role": UserRole.FACULTY,
                "full_name": "Dr. Faculty Member",
                "department": "Computer Science",
                "is_active": True,
                "first_login": False,
            },
            {
                "username": "student",
                "email": "student@pulseconnect.edu",
                "password": "student123",
                "role": UserRole.STUDENT,
                "full_name": "Student User",
                "department": "Computer Science",
                "year": "2024",
                "section": "A",
                "is_active": True,
                "first_login": False,
            },
        ]
        
        for user_data in demo_users:
            password = user_data.pop("password")
            user = User(
                **user_data,
                password_hash=get_password_hash(password),
                created_at=datetime.utcnow()
            )
            db.add(user)
        
        db.commit()
        
        print("\n✅ Demo users seeded successfully!")
        print("\nDemo Credentials:")
        print("=" * 60)
        print("Super Admin  -> username: root        | password: root123")
        print("Super Admin  -> username: superadmin  | password: admin123")
        print("College Admin-> username: collegeadmin| password: admin123")
        print("Faculty      -> username: faculty     | password: faculty123")
        print("Student      -> username: student     | password: student123")
        print("=" * 60)
        
    except Exception as e:
        print(f"Seed error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("PulseConnect Database Migration")
    print("=" * 60)
    migrate_database()
    seed_demo_users()
