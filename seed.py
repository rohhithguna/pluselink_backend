from database import SessionLocal, init_db
from models import User, Alert, Reaction, UserRole, AlertPriority
from auth import get_password_hash
from datetime import datetime, timedelta

def seed_database():
    init_db()
    
    db = SessionLocal()
    
    try:
        if db.query(User).count() > 0:
            print("Database already seeded")
            return
        
        users = [
            User(
                username="superadmin",
                email="superadmin@pulseconnect.edu",
                password_hash=get_password_hash("admin123"),
                role=UserRole.SUPER_ADMIN,
                full_name="Super Administrator",
                is_approved=True
            ),
            User(
                username="collegeadmin",
                email="admin@pulseconnect.edu",
                password_hash=get_password_hash("admin123"),
                role=UserRole.COLLEGE_ADMIN,
                full_name="College Administrator",
                is_approved=True
            ),
            User(
                username="faculty",
                email="faculty@pulseconnect.edu",
                password_hash=get_password_hash("faculty123"),
                role=UserRole.FACULTY,
                full_name="Dr. Faculty Member",
                is_approved=True
            ),
            User(
                username="student",
                email="student@pulseconnect.edu",
                password_hash=get_password_hash("student123"),
                role=UserRole.STUDENT,
                full_name="Student User",
                is_approved=True
            ),
        ]
        
        for user in users:
            db.add(user)
        
        db.commit()
        
        alerts = [
            Alert(
                title="🚨 Emergency Alert: Campus Lockdown",
                message="Please remain in your current location. Campus security is responding to an incident. Updates will follow.",
                priority=AlertPriority.EMERGENCY,
                sender_id=1,
                created_at=datetime.utcnow() - timedelta(hours=2)
            ),
            Alert(
                title="⚠️ Important: Library Hours Extended",
                message="The library will be open 24/7 during finals week starting Monday. All students have access.",
                priority=AlertPriority.IMPORTANT,
                sender_id=2,
                created_at=datetime.utcnow() - timedelta(hours=5)
            ),
            Alert(
                title="ℹ️ Info: New Course Registration Opens",
                message="Course registration for Spring semester opens next Monday at 8 AM. Check your advisor for requirements.",
                priority=AlertPriority.INFO,
                sender_id=2,
                created_at=datetime.utcnow() - timedelta(days=1)
            ),
            Alert(
                title="⏰ Reminder: Parking Permits Due",
                message="All parking permits for the semester must be purchased by Friday. Visit parking.edu to register.",
                priority=AlertPriority.REMINDER,
                sender_id=3,
                created_at=datetime.utcnow() - timedelta(days=2)
            ),
            Alert(
                title="🚨 Weather Alert: Severe Storm Warning",
                message="Severe thunderstorm expected between 3-6 PM. Avoid outdoor activities and seek shelter.",
                priority=AlertPriority.EMERGENCY,
                sender_id=1,
                created_at=datetime.utcnow() - timedelta(days=3)
            ),
        ]
        
        for alert in alerts:
            db.add(alert)
        
        db.commit()
        
        reactions = [
            Reaction(alert_id=1, user_id=3, emoji="👍"),
            Reaction(alert_id=1, user_id=4, emoji="👍"),
            Reaction(alert_id=2, user_id=4, emoji="🔥"),
            Reaction(alert_id=2, user_id=3, emoji="❤️"),
            Reaction(alert_id=3, user_id=4, emoji="👍"),
            Reaction(alert_id=4, user_id=3, emoji="👍"),
            Reaction(alert_id=4, user_id=4, emoji="😢"),
        ]
        
        for reaction in reactions:
            db.add(reaction)
        
        db.commit()
        
        print("Database seeded successfully!")
        print("\nDemo Credentials:")
        print("=" * 50)
        print("Super Admin  -> username: superadmin   | password: admin123")
        print("College Admin-> username: collegeadmin | password: admin123")
        print("Faculty      -> username: faculty      | password: faculty123")
        print("Student      -> username: student      | password: student123")
        print("=" * 50)
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
