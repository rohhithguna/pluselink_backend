"""
Migration script to add database indexes for improved performance.
Run this script to update an existing database with new indexes.
"""
from sqlalchemy import create_engine, text, inspect
from database import DATABASE_URL

def add_indexes():
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    print("Adding database indexes...")
    
    with engine.connect() as conn:
        try:
            indexes = inspector.get_indexes('alerts')
            if not any(idx['name'] == 'ix_alerts_created_at' for idx in indexes):
                conn.execute(text("CREATE INDEX ix_alerts_created_at ON alerts(created_at)"))
                print("✅ Added index: ix_alerts_created_at")
            else:
                print("⏭️  Index already exists: ix_alerts_created_at")
            
            if not any(idx['name'] == 'ix_alerts_is_active' for idx in indexes):
                conn.execute(text("CREATE INDEX ix_alerts_is_active ON alerts(is_active)"))
                print("✅ Added index: ix_alerts_is_active")
            else:
                print("⏭️  Index already exists: ix_alerts_is_active")
            
            indexes = inspector.get_indexes('reactions')
            if not any(idx['name'] == 'ix_reactions_alert_id' for idx in indexes):
                conn.execute(text("CREATE INDEX ix_reactions_alert_id ON reactions(alert_id)"))
                print("✅ Added index: ix_reactions_alert_id")
            else:
                print("⏭️  Index already exists: ix_reactions_alert_id")
            
            conn.commit()
            print("\n✅ All indexes added successfully!")
            
        except Exception as e:
            print(f"\n❌ Error adding indexes: {e}")
            conn.rollback()

if __name__ == "__main__":
    add_indexes()
