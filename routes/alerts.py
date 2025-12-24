from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import json
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import get_db
from models import Alert, User, UserRole, AlertPriority, AlertView, AlertCategory, AlertAcknowledgment, Reaction
from auth import get_current_user, require_role
from websocket_manager import ws_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
limiter = Limiter(key_func=get_remote_address)

class AlertCreate(BaseModel):
    title: str
    message: str
    priority: AlertPriority
    category: AlertCategory = AlertCategory.GENERAL
    target_roles: List[str] = ["all"]

class AlertResponse(BaseModel):
    id: int
    title: str
    message: str
    priority: str
    category: str
    sender_id: int
    sender_name: str
    created_at: datetime
    is_active: bool
    reaction_counts: dict
    target_roles: List[str] = ["all"]
    effectiveness_score: Optional[float] = None
    acknowledgment_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

def get_reaction_counts_for_alert(db: Session, alert_id: int) -> dict:
    """Get reaction counts using SQL aggregation for better performance"""
    from models import Reaction
    results = db.query(
        Reaction.emoji,
        func.count(Reaction.id).label('count')
    ).filter(
        Reaction.alert_id == alert_id
    ).group_by(Reaction.emoji).all()
    
    return {emoji: count for emoji, count in results}

def calculate_effectiveness_score(db: Session, alert_id: int, total_users: int = None) -> float:
    """Calculate effectiveness score (0-100) based on views, reactions, and acknowledgments"""
    if total_users is None:
        total_users = db.query(User).count()
    
    if total_users == 0:
        return 0.0
    
    view_count = db.query(AlertView).filter(AlertView.alert_id == alert_id).count()
    reaction_count = db.query(Reaction).filter(Reaction.alert_id == alert_id).count()
    ack_count = db.query(AlertAcknowledgment).filter(AlertAcknowledgment.alert_id == alert_id).count()
    
    view_rate = (view_count / total_users) * 100
    reaction_rate = (reaction_count / total_users) * 100
    ack_rate = (ack_count / total_users) * 100
    
    score = (view_rate * 0.4) + (ack_rate * 0.3) + (reaction_rate * 0.3)
    
    return min(round(score, 2), 100.0)

def normalize_target_roles(target_roles: List[str]) -> List[str]:
    """
    Normalize target roles to singular form.
    Accepts both 'students' and 'student', 'faculty' stays as is.
    """
    normalized = []
    for role in target_roles:
        role_lower = role.lower()
        if role_lower == 'students':
            normalized.append('student')
        else:
            normalized.append(role_lower)
    return normalized

def validate_target_roles(sender_role: UserRole, target_roles: List[str]) -> bool:
    """
    Validate if sender can send alerts to target roles.
    
    Rules:
    - Super Admin: can send to students, faculty, college_admin, all
    - College Admin: can send to faculty, students (NOT super_admin)
    - Faculty: can send to students only
    - Students: cannot send alerts (handled by route decorator)
    """
    normalized_roles = normalize_target_roles(target_roles)
    target_set = set(normalized_roles)
    
    if "all" in target_set:
        if sender_role == UserRole.SUPER_ADMIN or sender_role == UserRole.COLLEGE_ADMIN:
            return True
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to send alerts to all groups."
        )
    
    if sender_role == UserRole.SUPER_ADMIN:
        allowed = {"student", "faculty", "college_admin"}
        if not target_set.issubset(allowed):
            raise HTTPException(
                status_code=403,
                detail=f"Invalid target roles. Super Admin can send to: {', '.join(allowed)}"
            )
        return True
    
    if sender_role == UserRole.COLLEGE_ADMIN:
        allowed = {"student", "faculty"}
        if not target_set.issubset(allowed):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to send alerts to this group. College Admins can only send to Students and Faculty."
            )
        return True
    
    if sender_role == UserRole.FACULTY:
        if target_set != {"student"}:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to send alerts to this group. Faculty can only send to Students."
            )
        return True
    
    return False

@router.post("", response_model=AlertResponse)
@limiter.limit("10/minute")
async def create_alert(
    request: Request,
    alert: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN, UserRole.FACULTY))
):
    """Create a new alert (Admin/Faculty only)"""
    validate_target_roles(current_user.role, alert.target_roles)
    
    new_alert = Alert(
        title=alert.title,
        message=alert.message,
        priority=alert.priority,
        category=alert.category,
        sender_id=current_user.id,
        target_roles=json.dumps(alert.target_roles)
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)
    
    alert_data = {
        "id": new_alert.id,
        "title": new_alert.title,
        "message": new_alert.message,
        "priority": new_alert.priority.value,
        "category": new_alert.category.value,
        "sender_id": new_alert.sender_id,
        "sender_name": current_user.full_name or current_user.username,
        "created_at": new_alert.created_at.isoformat(),
        "is_active": new_alert.is_active,
        "reaction_counts": {},
        "target_roles": alert.target_roles,
        "effectiveness_score": None,
        "acknowledgment_count": 0
    }
    
    await ws_manager.broadcast_alert(alert_data, target_roles=alert.target_roles)
    
    return AlertResponse(
        id=new_alert.id,
        title=new_alert.title,
        message=new_alert.message,
        priority=new_alert.priority.value,
        category=new_alert.category.value,
        sender_id=new_alert.sender_id,
        sender_name=current_user.full_name or current_user.username,
        created_at=new_alert.created_at,
        is_active=new_alert.is_active,
        reaction_counts={},
        target_roles=alert.target_roles,
        effectiveness_score=None,
        acknowledgment_count=0
    )

@router.get("", response_model=List[AlertResponse])
def get_alerts(
    skip: int = 0,
    limit: int = 50,
    priority: str = None,
    category: str = None,
    search: str = None,
    start_date: str = None,
    end_date: str = None,
    sender_id: int = None,
    include_expired: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all alerts with advanced filtering, search, auto-expiration, and role-based visibility"""
    query = db.query(Alert).filter(Alert.is_active == True)
    
    if not include_expired:
        now = datetime.utcnow()
        low_priority_cutoff = now - timedelta(hours=24)
        
        from sqlalchemy import or_, and_
        query = query.filter(
            or_(
                Alert.priority.in_([AlertPriority.EMERGENCY, AlertPriority.IMPORTANT]),
                Alert.created_at >= low_priority_cutoff
            )
        )
    
    all_alerts = query.order_by(Alert.created_at.desc()).all()
    
    
    user_role = current_user.role.value
    
    filtered_alerts = []
    for alert in all_alerts:
        target_roles = json.loads(alert.target_roles) if alert.target_roles else ["all"]
        
        target_roles = [r.lower() for r in target_roles]
        
        should_see = False
        
        if "all" in target_roles or "global" in target_roles:
            should_see = True
        elif user_role in ["super_admin", "college_admin"]:
            if user_role in target_roles:
                should_see = True
            elif alert.sender_id == current_user.id:
                should_see = True
        elif user_role == "student":
            if "student" in target_roles:
                should_see = True
        elif user_role == "faculty":
            if "faculty" in target_roles:
                should_see = True
        
        if should_see:
            filtered_alerts.append(alert)
    
    final_alerts = []
    for alert in filtered_alerts:
        if priority:
            try:
                priority_enum = AlertPriority(priority)
                if alert.priority != priority_enum:
                    continue
            except ValueError:
                pass
        
        if category:
            try:
                category_enum = AlertCategory(category)
                if alert.category != category_enum:
                    continue
            except ValueError:
                pass
        
        if search:
            search_lower = search.lower()
            if search_lower not in alert.title.lower() and search_lower not in alert.message.lower():
                continue
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                if alert.created_at < start_dt:
                    continue
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                if alert.created_at > end_dt:
                    continue
            except ValueError:
                pass
        
        if sender_id:
            if alert.sender_id != sender_id:
                continue
        
        final_alerts.append(alert)
    
    paginated_alerts = final_alerts[skip:skip + limit]
    
    total_users = db.query(User).count()
    
    result = []
    for alert in paginated_alerts:
        reaction_counts = get_reaction_counts_for_alert(db, alert.id)
        target_roles = json.loads(alert.target_roles) if alert.target_roles else ["all"]
        
        ack_count = db.query(AlertAcknowledgment).filter(
            AlertAcknowledgment.alert_id == alert.id
        ).count()
        
        effectiveness_score = alert.effectiveness_score
        if effectiveness_score is None:
            effectiveness_score = calculate_effectiveness_score(db, alert.id, total_users)
            alert.effectiveness_score = effectiveness_score
            db.commit()
        
        result.append(AlertResponse(
            id=alert.id,
            title=alert.title,
            message=alert.message,
            priority=alert.priority.value,
            category=alert.category.value,
            sender_id=alert.sender_id,
            sender_name=alert.sender.full_name or alert.sender.username,
            created_at=alert.created_at,
            is_active=alert.is_active,
            reaction_counts=reaction_counts,
            target_roles=target_roles,
            effectiveness_score=effectiveness_score,
            acknowledgment_count=ack_count
        ))
    
    return result

@router.get("/history", response_model=List[AlertResponse])
def get_alert_history(
    skip: int = 0,
    limit: int = 100,
    priority: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all alerts including inactive ones for history view (with role-based filtering)"""
    query = db.query(Alert)
    
    if priority:
        try:
            priority_enum = AlertPriority(priority)
            query = query.filter(Alert.priority == priority_enum)
        except ValueError:
            pass
    
    all_alerts = query.order_by(Alert.created_at.desc()).all()
    
    user_role = current_user.role.value
    
    filtered_alerts = []
    for alert in all_alerts:
        target_roles = json.loads(alert.target_roles) if alert.target_roles else ["all"]
        target_roles = [r.lower() for r in target_roles]
        
        should_see = False
        
        if "all" in target_roles or "global" in target_roles:
            should_see = True
        elif user_role in ["super_admin", "college_admin"]:
            if user_role in target_roles or alert.sender_id == current_user.id:
                should_see = True
        elif user_role == "student":
            if "student" in target_roles:
                should_see = True
        elif user_role == "faculty":
            if "faculty" in target_roles:
                should_see = True
        
        if should_see:
            filtered_alerts.append(alert)
    
    paginated_alerts = filtered_alerts[skip:skip + limit]
    
    result = []
    for alert in paginated_alerts:
        reaction_counts = get_reaction_counts_for_alert(db, alert.id)
        
        target_roles = json.loads(alert.target_roles) if alert.target_roles else ["all"]
        
        result.append(AlertResponse(
            id=alert.id,
            title=alert.title,
            message=alert.message,
            priority=alert.priority.value,
            category=alert.category.value if alert.category else AlertCategory.GENERAL.value,
            sender_id=alert.sender_id,
            sender_name=alert.sender.full_name or alert.sender.username,
            created_at=alert.created_at,
            is_active=alert.is_active,
            reaction_counts=reaction_counts,
            target_roles=target_roles
        ))
    
    return result

@router.post("/{alert_id}/view")
async def mark_alert_viewed(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark an alert as viewed by the current user"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    existing_view = db.query(AlertView).filter(
        AlertView.alert_id == alert_id,
        AlertView.user_id == current_user.id
    ).first()
    
    if not existing_view:
        view = AlertView(alert_id=alert_id, user_id=current_user.id)
        db.add(view)
        db.commit()
    
    return {"status": "success"}

@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN))
):
    """Delete/deactivate an alert (Admin only)"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_active = False
    db.commit()
    
    await ws_manager.broadcast_alert_deletion(alert_id)
    
    return {"status": "success"}

@router.delete("/{alert_id}/permanent")
async def permanent_delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """Permanently delete an alert from database (Super Admin only)"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    db.query(Reaction).filter(Reaction.alert_id == alert_id).delete()
    db.query(AlertView).filter(AlertView.alert_id == alert_id).delete()
    db.query(AlertAcknowledgment).filter(AlertAcknowledgment.alert_id == alert_id).delete()
    
    db.delete(alert)
    db.commit()
    
    await ws_manager.broadcast_alert_deletion(alert_id)
    
    return {"status": "success", "message": "Alert permanently deleted"}

class BulkDeleteRequest(BaseModel):
    alert_ids: List[int]

class BulkDeleteResponse(BaseModel):
    deleted_ids: List[int]
    message: str

@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_alerts(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN))
):
    """
    Bulk delete/deactivate alerts (Admin only).
    Deactivates all specified alerts and broadcasts deletion to all connected users.
    Returns list of deleted IDs for undo functionality.
    """
    deleted_ids = []
    
    for alert_id in request.alert_ids:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert and alert.is_active:
            alert.is_active = False
            deleted_ids.append(alert_id)
            await ws_manager.broadcast_alert_deletion(alert_id)
    
    db.commit()
    
    return BulkDeleteResponse(
        deleted_ids=deleted_ids,
        message=f"Successfully deleted {len(deleted_ids)} alert(s)"
    )

@router.post("/bulk-restore", response_model=BulkDeleteResponse)
async def bulk_restore_alerts(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN))
):
    """
    Bulk restore/reactivate alerts (Admin only).
    Used for undo functionality after bulk delete.
    """
    restored_ids = []
    
    for alert_id in request.alert_ids:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert and not alert.is_active:
            alert.is_active = True
            restored_ids.append(alert_id)
    
    db.commit()
    
    return BulkDeleteResponse(
        deleted_ids=restored_ids,
        message=f"Successfully restored {len(restored_ids)} alert(s)"
    )
