from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from database import get_db
from models import Alert, Reaction, User, AlertView, AlertPriority
from auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall statistics"""
    total_alerts = db.query(Alert).count()
    active_alerts = db.query(Alert).filter(Alert.is_active == True).count()
    total_reactions = db.query(Reaction).count()
    total_users = db.query(User).count()
    
    return {
        "total_alerts": total_alerts,
        "active_alerts": active_alerts,
        "total_reactions": total_reactions,
        "total_users": total_users
    }

@router.get("/alerts-by-priority")
def get_alerts_by_priority(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get alert counts grouped by priority"""
    results = db.query(
        Alert.priority,
        func.count(Alert.id).label('count')
    ).group_by(Alert.priority).all()
    
    data = []
    for priority, count in results:
        data.append({
            "priority": priority.value,
            "count": count
        })
    
    return data

@router.get("/alerts-over-time")
def get_alerts_over_time(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get alert counts over time"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    alerts = db.query(Alert).filter(
        Alert.created_at >= start_date
    ).all()
    
    date_counts = {}
    for alert in alerts:
        date_key = alert.created_at.strftime('%Y-%m-%d')
        if date_key not in date_counts:
            date_counts[date_key] = 0
        date_counts[date_key] += 1
    
    data = []
    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.strftime('%Y-%m-%d')
        data.append({
            "date": date_key,
            "count": date_counts.get(date_key, 0)
        })
        current_date += timedelta(days=1)
    
    return data

@router.get("/top-reactions")
def get_top_reactions(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get most used reaction emojis"""
    results = db.query(
        Reaction.emoji,
        func.count(Reaction.id).label('count')
    ).group_by(Reaction.emoji).order_by(func.count(Reaction.id).desc()).limit(limit).all()
    
    data = []
    for emoji, count in results:
        data.append({
            "emoji": emoji,
            "count": count
        })
    
    return data

@router.get("/engagement")
def get_engagement_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user engagement statistics"""
    total_alerts = db.query(Alert).count()
    total_views = db.query(AlertView).count()
    total_reactions = db.query(Reaction).count()
    
    view_rate = (total_views / total_alerts * 100) if total_alerts > 0 else 0
    reaction_rate = (total_reactions / total_alerts * 100) if total_alerts > 0 else 0
    
    return {
        "total_views": total_views,
        "total_reactions": total_reactions,
        "view_rate": round(view_rate, 2),
        "reaction_rate": round(reaction_rate, 2)
    }
