"""
Admin Analytics API Routes for Control Center
Only accessible by super_admin role
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from database import get_db
from models import User, UserRole, Alert, ActivityLog, ActivityType, AlertAcknowledgment, Reaction
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/admin", tags=["admin-analytics"])


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_alerts: int
    active_alerts: int
    users_by_role: dict
    total_acknowledgments: int
    total_reactions: int

class LoginStats(BaseModel):
    date: str
    count: int

class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    activity_type: str
    description: str
    ip_address: Optional[str]
    created_at: datetime


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get summary statistics for super admin control center.
    """
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    
    role_counts = {}
    for role in UserRole:
        count = db.query(func.count(User.id)).filter(User.role == role).scalar()
        role_counts[role.value] = count
    
    total_alerts = db.query(func.count(Alert.id)).scalar()
    active_alerts = db.query(func.count(Alert.id)).filter(Alert.is_active == True).scalar()
    
    total_acks = db.query(func.count(AlertAcknowledgment.id)).scalar()
    total_reactions = db.query(func.count(Reaction.id)).scalar()
    
    return DashboardStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_alerts=total_alerts or 0,
        active_alerts=active_alerts or 0,
        users_by_role=role_counts,
        total_acknowledgments=total_acks or 0,
        total_reactions=total_reactions or 0
    )


@router.get("/logins", response_model=List[LoginStats])
async def get_login_stats(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get login counts per day for the last N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    login_logs = db.query(
        func.date(ActivityLog.created_at).label('date'),
        func.count(ActivityLog.id).label('count')
    ).filter(
        ActivityLog.activity_type == ActivityType.LOGIN,
        ActivityLog.created_at >= start_date
    ).group_by(
        func.date(ActivityLog.created_at)
    ).order_by(
        func.date(ActivityLog.created_at)
    ).all()
    
    result = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days-1-i)).strftime("%Y-%m-%d")
        count = 0
        for log in login_logs:
            if str(log.date) == date:
                count = log.count
                break
        result.append(LoginStats(date=date, count=count))
    
    return result


@router.get("/alerts-by-role")
async def get_alerts_by_role(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get alert counts grouped by sender role.
    """
    results = db.query(
        User.role,
        func.count(Alert.id).label('count')
    ).join(
        Alert, Alert.sender_id == User.id
    ).group_by(
        User.role
    ).all()
    
    data = {}
    for role in UserRole:
        data[role.value] = 0
    
    for role, count in results:
        data[role.value] = count
    
    return {"alerts_by_role": data}


@router.get("/activity-log", response_model=List[ActivityLogResponse])
async def get_activity_log(
    limit: int = 50,
    activity_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get recent activity log entries.
    """
    query = db.query(ActivityLog).order_by(ActivityLog.created_at.desc())
    
    if activity_type:
        try:
            at = ActivityType(activity_type)
            query = query.filter(ActivityLog.activity_type == at)
        except ValueError:
            pass
    
    logs = query.limit(limit).all()
    
    user_ids = [log.user_id for log in logs if log.user_id]
    users = {}
    if user_ids:
        user_records = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u.username for u in user_records}
    
    return [
        ActivityLogResponse(
            id=log.id,
            user_id=log.user_id,
            username=users.get(log.user_id) if log.user_id else None,
            activity_type=log.activity_type.value if log.activity_type else "unknown",
            description=log.description,
            ip_address=log.ip_address,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/online-users")
async def get_online_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get users who logged in within the last 15 minutes (approximately online).
    """
    threshold = datetime.utcnow() - timedelta(minutes=15)
    
    online_users = db.query(User).filter(
        User.last_login_at >= threshold,
        User.is_active == True
    ).all()
    
    return {
        "count": len(online_users),
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role.value,
                "last_login_at": u.last_login_at
            }
            for u in online_users
        ]
    }
