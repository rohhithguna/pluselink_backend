from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    COLLEGE_ADMIN = "college_admin"
    FACULTY = "faculty"
    STUDENT = "student"

class AlertPriority(str, enum.Enum):
    EMERGENCY = "emergency"
    IMPORTANT = "important"
    INFO = "info"
    REMINDER = "reminder"

class AlertCategory(str, enum.Enum):
    EMERGENCY = "emergency"
    ACADEMIC = "academic"
    EVENT = "event"
    MAINTENANCE = "maintenance"
    WEATHER = "weather"
    GENERAL = "general"

class ActivityType(str, enum.Enum):
    """Activity types for security logging"""
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE_ALERT = "create_alert"
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    RESET_PASSWORD = "reset_password"
    UPDATE_PROFILE = "update_profile"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String, nullable=False)
    
    department = Column(String, nullable=True)
    year = Column(String, nullable=True)
    section = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    first_login = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    
    settings_json = Column(String, nullable=True)
    
    sent_alerts = relationship("Alert", back_populates="sender", foreign_keys="Alert.sender_id")
    reactions = relationship("Reaction", back_populates="user")
    alert_views = relationship("AlertView", back_populates="user")
    acknowledgments = relationship("AlertAcknowledgment", back_populates="user")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
    created_templates = relationship("AlertTemplate", back_populates="created_by")
    badges = relationship("UserBadge", back_populates="user")


class ActivityLog(Base):
    """Security activity log for audit trail"""
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    activity_type = Column(Enum(ActivityType), nullable=False)
    description = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    extra_data = Column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    priority = Column(Enum(AlertPriority), nullable=False)
    category = Column(Enum(AlertCategory), default=AlertCategory.GENERAL, nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    target_roles = Column(String, default='["all"]')
    effectiveness_score = Column(Float, nullable=True)
    
    sender = relationship("User", back_populates="sent_alerts", foreign_keys=[sender_id])
    reactions = relationship("Reaction", back_populates="alert", cascade="all, delete-orphan")
    views = relationship("AlertView", back_populates="alert", cascade="all, delete-orphan")
    acknowledgments = relationship("AlertAcknowledgment", back_populates="alert", cascade="all, delete-orphan")

class Reaction(Base):
    __tablename__ = "reactions"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    emoji = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    alert = relationship("Alert", back_populates="reactions")
    user = relationship("User", back_populates="reactions")

class AlertView(Base):
    __tablename__ = "alert_views"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.utcnow)
    
    alert = relationship("Alert", back_populates="views")
    user = relationship("User", back_populates="alert_views")

class AlertAcknowledgment(Base):
    __tablename__ = "alert_acknowledgments"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    acknowledged_at = Column(DateTime, default=datetime.utcnow)
    
    alert = relationship("Alert", back_populates="acknowledgments")
    user = relationship("User", back_populates="acknowledgments")

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    mute_emergency = Column(Boolean, default=False)
    mute_important = Column(Boolean, default=False)
    mute_info = Column(Boolean, default=False)
    mute_reminder = Column(Boolean, default=False)
    
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String, default="22:00")
    quiet_hours_end = Column(String, default="08:00")
    
    user = relationship("User", back_populates="preferences")

class AlertTemplate(Base):
    __tablename__ = "alert_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    priority = Column(Enum(AlertPriority), nullable=False)
    category = Column(Enum(AlertCategory), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    created_by = relationship("User", back_populates="created_templates")


class BadgeType(str, enum.Enum):
    """Badge types awarded based on user activity"""
    FAST_RESPONDER = "fast_responder"
    PRECISION_REPORTER = "precision_reporter"
    COMMUNITY_HELPER = "community_helper"
    CRISIS_GUARDIAN = "crisis_guardian"
    PRIORITY_SUPPORTER = "priority_supporter"


class UserBadge(Base):
    """Tracks badges earned by users"""
    __tablename__ = "user_badges"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_type = Column(Enum(BadgeType), nullable=False)
    earned_at = Column(DateTime, default=datetime.utcnow)
    is_new = Column(Boolean, default=True)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
    
    user = relationship("User", back_populates="badges")
