"""
Migration script to add is_approved and gender columns to the users table.
Also marks existing users as approved (they are demo/seeded users).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pulseconnect.db"


def migrate():
    """Add is_approved and gender columns to users table."""
    if not DB_PATH.exists():
        print("Database not found. Nothing to migrate.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "is_approved" not in columns:
            print("Adding 'is_approved' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT 0 NOT NULL")
            cursor.execute("UPDATE users SET is_approved = 1")
            print("✅ Added 'is_approved' column and marked existing users as approved")
        else:
            print("ℹ️  'is_approved' column already exists")
        
        if "gender" not in columns:
            print("Adding 'gender' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT")
            print("✅ Added 'gender' column")
        else:
            print("ℹ️  'gender' column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
