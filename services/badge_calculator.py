"""
Badge Calculator Service
Calculates and awards badges based on user activity
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import (
    User, UserBadge, BadgeType, Alert, AlertAcknowledgment, 
    Reaction, AlertPriority
)


BADGE_INFO = {
    BadgeType.FAST_RESPONDER: {
        "icon": "⚡",
        "name": "Fast Responder",
        "description": "Acknowledges alerts within 5 minutes"
    },
    BadgeType.PRECISION_REPORTER: {
        "icon": "🎯",
        "name": "Precision Reporter",
        "description": "Creates verified helpful alerts"
    },
    BadgeType.COMMUNITY_HELPER: {
        "icon": "🧭",
        "name": "Community Helper",
        "description": "Actively helps the community with reactions"
    },
    BadgeType.CRISIS_GUARDIAN: {
        "icon": "🛡",
        "name": "Crisis Guardian",
        "description": "Active during emergency mode"
    },
    BadgeType.PRIORITY_SUPPORTER: {
        "icon": "🔥",
        "name": "Priority Supporter",
        "description": "Top 5% response rate weekly"
    }
}


def get_badge_info(badge_type: BadgeType) -> dict:
    """Get badge info (icon, name, description)"""
    return BADGE_INFO.get(badge_type, {})


def award_badge(db: Session, user_id: int, badge_type: BadgeType) -> bool:
    """
    Award a badge to a user if they don't already have it.
    Returns True if badge was newly awarded, False if already had it.
    """
    existing = db.query(UserBadge).filter(
        UserBadge.user_id == user_id,
        UserBadge.badge_type == badge_type
    ).first()
    
    if existing:
        return False
    
    new_badge = UserBadge(
        user_id=user_id,
        badge_type=badge_type,
        is_new=True
    )
    db.add(new_badge)
    db.commit()
    return True


def calculate_fast_responder(db: Session, user_id: int) -> bool:
    """
    Award Fast Responder badge if user has acknowledged
    at least 5 alerts within 5 minutes of creation.
    """
    fast_acks = db.query(AlertAcknowledgment).join(Alert).filter(
        AlertAcknowledgment.user_id == user_id,
        AlertAcknowledgment.acknowledged_at <= Alert.created_at + timedelta(minutes=5)
    ).count()
    
    if fast_acks >= 5:
        return award_badge(db, user_id, BadgeType.FAST_RESPONDER)
    return False


def calculate_precision_reporter(db: Session, user_id: int) -> bool:
    """
    Award Precision Reporter badge if user has created
    at least 3 alerts with effectiveness score >= 70.
    """
    high_quality_alerts = db.query(Alert).filter(
        Alert.sender_id == user_id,
        Alert.effectiveness_score >= 70
    ).count()
    
    if high_quality_alerts >= 3:
        return award_badge(db, user_id, BadgeType.PRECISION_REPORTER)
    return False


def calculate_community_helper(db: Session, user_id: int) -> bool:
    """
    Award Community Helper badge if user has reacted
    to at least 10 alerts with helpful reactions.
    """
    reaction_count = db.query(Reaction).filter(
        Reaction.user_id == user_id
    ).count()
    
    if reaction_count >= 10:
        return award_badge(db, user_id, BadgeType.COMMUNITY_HELPER)
    return False


def calculate_crisis_guardian(db: Session, user_id: int) -> bool:
    """
    Award Crisis Guardian badge if user has acknowledged
    at least 3 emergency alerts.
    """
    emergency_acks = db.query(AlertAcknowledgment).join(Alert).filter(
        AlertAcknowledgment.user_id == user_id,
        Alert.priority == AlertPriority.EMERGENCY
    ).count()
    
    if emergency_acks >= 3:
        return award_badge(db, user_id, BadgeType.CRISIS_GUARDIAN)
    return False


def calculate_priority_supporter(db: Session, user_id: int) -> bool:
    """
    Award Priority Supporter badge if user is in top 5%
    of acknowledgment response rate in the past week.
    """
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    
    user_ack_counts = db.query(
        AlertAcknowledgment.user_id,
        func.count(AlertAcknowledgment.id).label('count')
    ).filter(
        AlertAcknowledgment.acknowledged_at >= one_week_ago
    ).group_by(AlertAcknowledgment.user_id).all()
    
    if not user_ack_counts:
        return False
    
    user_count = next((c.count for c in user_ack_counts if c.user_id == user_id), 0)
    
    if user_count == 0:
        return False
    
    all_counts = sorted([c.count for c in user_ack_counts], reverse=True)
    top_5_percent_index = max(0, int(len(all_counts) * 0.05))
    threshold = all_counts[top_5_percent_index] if all_counts else 0
    
    if user_count >= threshold and user_count > 0:
        return award_badge(db, user_id, BadgeType.PRIORITY_SUPPORTER)
    return False


def calculate_all_badges(db: Session, user_id: int) -> list:
    """
    Calculate and award all eligible badges for a user.
    Returns list of newly awarded badge types.
    """
    newly_awarded = []
    
    if calculate_fast_responder(db, user_id):
        newly_awarded.append(BadgeType.FAST_RESPONDER)
    
    if calculate_precision_reporter(db, user_id):
        newly_awarded.append(BadgeType.PRECISION_REPORTER)
    
    if calculate_community_helper(db, user_id):
        newly_awarded.append(BadgeType.COMMUNITY_HELPER)
    
    if calculate_crisis_guardian(db, user_id):
        newly_awarded.append(BadgeType.CRISIS_GUARDIAN)
    
    if calculate_priority_supporter(db, user_id):
        newly_awarded.append(BadgeType.PRIORITY_SUPPORTER)
    
    return newly_awarded


def get_user_badges(db: Session, user_id: int) -> list:
    """Get all badges for a user with info"""
    badges = db.query(UserBadge).filter(
        UserBadge.user_id == user_id
    ).order_by(UserBadge.earned_at.desc()).all()
    
    result = []
    for badge in badges:
        info = get_badge_info(badge.badge_type)
        result.append({
            "type": badge.badge_type.value,
            "icon": info.get("icon", "🏅"),
            "name": info.get("name", "Badge"),
            "description": info.get("description", ""),
            "earned_at": badge.earned_at.isoformat(),
            "is_new": badge.is_new
        })
    
    return result
