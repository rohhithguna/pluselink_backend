"""
Migration script to add new features to PulseConnect database.
This adds: Alert Categories, Acknowledgments, User Preferences, Templates, and Effectiveness Score.
"""
from sqlalchemy import create_engine, text, inspect
from database import DATABASE_URL, Base
from models import (
    AlertAcknowledgment, UserPreferences, AlertTemplate,
    Alert, User, Reaction, AlertView
)

def migrate_database():
    print("🔧 Starting database migration for new features...")
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    existing_tables = inspector.get_table_names()
    print(f"📊 Found {len(existing_tables)} existing tables")
    
    with engine.connect() as conn:
        try:
            print("\n1️⃣ Adding new columns to alerts table...")
            
            columns = [col['name'] for col in inspector.get_columns('alerts')]
            
            if 'category' not in columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN category VARCHAR DEFAULT 'general'"))
                print("   ✅ Added 'category' column")
            else:
                print("   ⏭️  'category' column already exists")
            
            if 'effectiveness_score' not in columns:
                conn.execute(text("ALTER TABLE alerts ADD COLUMN effectiveness_score FLOAT"))
                print("   ✅ Added 'effectiveness_score' column")
            else:
                print("   ⏭️  'effectiveness_score' column already exists")
            
            conn.commit()
            
            print("\n2️⃣ Creating new tables...")
            
            Base.metadata.create_all(bind=engine)
            
            new_tables = ['alert_acknowledgments', 'user_preferences', 'alert_templates']
            for table in new_tables:
                if table in inspector.get_table_names():
                    print(f"   ✅ Table '{table}' created/verified")
            
            conn.commit()
            
            print("\n✅ Migration completed successfully!")
            print("\n📋 Summary:")
            print("   - Added 'category' and 'effectiveness_score' to alerts")
            print("   - Created 'alert_acknowledgments' table")
            print("   - Created 'user_preferences' table")
            print("   - Created 'alert_templates' table")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate_database()
