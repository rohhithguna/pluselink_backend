"""
Alert Timeline API Routes
Provides detailed timeline data for incident playback
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models import Alert, User, UserRole, AlertView, Reaction, AlertAcknowledgment
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/alerts", tags=["timeline"])


class TimelineEvent(BaseModel):
    """Single event in the timeline"""
    event_type: str
    timestamp: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    details: Optional[dict] = None


class TimelineResponse(BaseModel):
    """Full timeline for an alert"""
    alert_id: int
    alert_title: str
    alert_priority: str
    created_at: str
    status: str
    events: List[TimelineEvent]
    total_views: int
    total_reactions: int
    total_acknowledgments: int


@router.get("/{alert_id}/timeline", response_model=TimelineResponse)
def get_alert_timeline(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN, UserRole.FACULTY))
):
    """
    Get detailed timeline for an alert (Admin/Faculty only)
    Returns chronological list of all events related to the alert
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    events = []
    
    sender = db.query(User).filter(User.id == alert.sender_id).first()
    events.append(TimelineEvent(
        event_type="created",
        timestamp=alert.created_at.isoformat(),
        user_id=alert.sender_id,
        user_name=sender.full_name or sender.username if sender else "Unknown",
        user_role=sender.role.value if sender else None,
        details={"priority": alert.priority.value, "category": alert.category.value}
    ))
    
    views = db.query(AlertView).filter(AlertView.alert_id == alert_id).order_by(AlertView.viewed_at).all()
    for view in views:
        viewer = db.query(User).filter(User.id == view.user_id).first()
        events.append(TimelineEvent(
            event_type="viewed",
            timestamp=view.viewed_at.isoformat(),
            user_id=view.user_id,
            user_name=viewer.full_name or viewer.username if viewer else "Unknown",
            user_role=viewer.role.value if viewer else None
        ))
    
    reactions = db.query(Reaction).filter(Reaction.alert_id == alert_id).order_by(Reaction.created_at).all()
    for reaction in reactions:
        reactor = db.query(User).filter(User.id == reaction.user_id).first()
        events.append(TimelineEvent(
            event_type="reaction",
            timestamp=reaction.created_at.isoformat(),
            user_id=reaction.user_id,
            user_name=reactor.full_name or reactor.username if reactor else "Unknown",
            user_role=reactor.role.value if reactor else None,
            details={"emoji": reaction.emoji}
        ))
    
    acks = db.query(AlertAcknowledgment).filter(AlertAcknowledgment.alert_id == alert_id).order_by(AlertAcknowledgment.acknowledged_at).all()
    for ack in acks:
        user = db.query(User).filter(User.id == ack.user_id).first()
        events.append(TimelineEvent(
            event_type="acknowledged",
            timestamp=ack.acknowledged_at.isoformat(),
            user_id=ack.user_id,
            user_name=user.full_name or user.username if user else "Unknown",
            user_role=user.role.value if user else None
        ))
    
    events.sort(key=lambda e: e.timestamp)
    
    status = "active" if alert.is_active else "resolved"
    
    from datetime import timedelta
    if alert.priority.value in ['info', 'reminder']:
        if datetime.utcnow() - alert.created_at > timedelta(hours=24):
            status = "expired"
    
    return TimelineResponse(
        alert_id=alert.id,
        alert_title=alert.title,
        alert_priority=alert.priority.value,
        created_at=alert.created_at.isoformat(),
        status=status,
        events=events,
        total_views=len(views),
        total_reactions=len(reactions),
        total_acknowledgments=len(acks)
    )
