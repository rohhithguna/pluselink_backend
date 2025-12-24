from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from pydantic import BaseModel
from database import get_db
from models import AlertAcknowledgment, Alert, User
from auth import get_current_user

router = APIRouter(prefix="/api/acknowledgments", tags=["acknowledgments"])

class AcknowledgmentResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    acknowledged_at: str
    
    class Config:
        from_attributes = True

class AcknowledgmentStatsResponse(BaseModel):
    alert_id: int
    total_users: int
    acknowledged_count: int
    acknowledgment_rate: float
    user_list: List[dict]

@router.post("/alert/{alert_id}")
async def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """User acknowledges an alert"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    existing = db.query(AlertAcknowledgment).filter(
        AlertAcknowledgment.alert_id == alert_id,
        AlertAcknowledgment.user_id == current_user.id
    ).first()
    
    if existing:
        return {"status": "already_acknowledged", "acknowledgment": {
            "id": existing.id,
            "alert_id": existing.alert_id,
            "user_id": existing.user_id,
            "acknowledged_at": existing.acknowledged_at.isoformat()
        }}
    
    acknowledgment = AlertAcknowledgment(
        alert_id=alert_id,
        user_id=current_user.id
    )
    db.add(acknowledgment)
    db.commit()
    db.refresh(acknowledgment)
    
    ack_count = db.query(AlertAcknowledgment).filter(
        AlertAcknowledgment.alert_id == alert_id
    ).count()
    
    from websocket_manager import ws_manager
    await ws_manager.broadcast_acknowledgment({
        "alert_id": alert_id,
        "count": ack_count,
        "user_id": current_user.id,
        "action": "add"
    })
    
    return {
        "status": "acknowledged",
        "acknowledgment": {
            "id": acknowledgment.id,
            "alert_id": acknowledgment.alert_id,
            "user_id": acknowledgment.user_id,
            "acknowledged_at": acknowledgment.acknowledged_at.isoformat()
        }
    }

@router.delete("/alert/{alert_id}")
async def unacknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """User removes their acknowledgment"""
    acknowledgment = db.query(AlertAcknowledgment).filter(
        AlertAcknowledgment.alert_id == alert_id,
        AlertAcknowledgment.user_id == current_user.id
    ).first()
    
    if not acknowledgment:
        raise HTTPException(status_code=404, detail="Acknowledgment not found")
    
    db.delete(acknowledgment)
    db.commit()
    
    return {"status": "unacknowledged"}

@router.get("/alert/{alert_id}/stats", response_model=AcknowledgmentStatsResponse)
def get_acknowledgment_stats(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get acknowledgment statistics for an alert"""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    acknowledgments = db.query(AlertAcknowledgment).filter(
        AlertAcknowledgment.alert_id == alert_id
    ).all()
    
    total_users = db.query(User).count()
    acknowledged_count = len(acknowledgments)
    
    acknowledgment_rate = (acknowledged_count / total_users * 100) if total_users > 0 else 0
    
    user_list = []
    for ack in acknowledgments:
        user = db.query(User).filter(User.id == ack.user_id).first()
        if user:
            user_list.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name or user.username,
                "acknowledged_at": ack.acknowledged_at.isoformat()
            })
    
    return AcknowledgmentStatsResponse(
        alert_id=alert_id,
        total_users=total_users,
        acknowledged_count=acknowledged_count,
        acknowledgment_rate=round(acknowledgment_rate, 2),
        user_list=user_list
    )
