"""
Migration script to add settings_json column to users table
Run this once to add the new column for UI settings cloud sync
"""
from sqlalchemy import text
from database import engine

def migrate():
    """Add settings_json column to users table if it doesn't exist"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'settings_json' not in columns:
            print("Adding settings_json column to users table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN settings_json TEXT"))
            conn.commit()
            print("✅ settings_json column added successfully")
        else:
            print("✅ settings_json column already exists")

if __name__ == "__main__":
    migrate()
