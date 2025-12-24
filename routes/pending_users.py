"""
Pending User Approval API Routes
Only accessible by super_admin role
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json

from database import get_db
from models import User, UserRole, ActivityLog, ActivityType
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/admin/pending-users", tags=["pending-users"])


class PendingUserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    role: str
    email: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ApprovalResponse(BaseModel):
    status: str
    message: str
    user_id: int


def log_activity(
    db: Session,
    user_id: int,
    activity_type: ActivityType,
    description: str,
    ip_address: str = None,
    metadata: dict = None
):
    """Log user activity for audit trail"""
    log = ActivityLog(
        user_id=user_id,
        activity_type=activity_type,
        description=description,
        ip_address=ip_address,
        extra_data=json.dumps(metadata) if metadata else None,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()


@router.get("/", response_model=List[PendingUserResponse])
async def list_pending_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    List all users pending approval.
    Only accessible by super_admin.
    """
    pending_users = db.query(User).filter(User.is_approved == False).order_by(User.created_at.desc()).all()
    
    return [
        PendingUserResponse(
            id=u.id,
            full_name=u.full_name or u.username,
            username=u.username,
            role=u.role.value,
            email=u.email,
            phone=getattr(u, 'phone', None),
            gender=getattr(u, 'gender', None),
            created_at=u.created_at
        )
        for u in pending_users
    ]


@router.get("/count")
async def get_pending_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get count of pending users for badge/notification.
    Only accessible by super_admin.
    """
    count = db.query(User).filter(User.is_approved == False).count()
    return {"pending_count": count}


@router.post("/{user_id}/approve", response_model=ApprovalResponse)
async def approve_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Approve a pending user.
    Sets is_approved=True and is_active=True.
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already approved"
        )
    
    user.is_approved = True
    user.is_active = True
    db.commit()
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.UPDATE_USER,
        f"Approved user: {user.username} ({user.role.value})",
        ip_address=client_ip,
        metadata={"approved_user_id": user.id, "username": user.username, "role": user.role.value}
    )
    
    return ApprovalResponse(
        status="approved",
        message=f"User '{user.username}' has been approved and can now log in.",
        user_id=user.id
    )


@router.post("/{user_id}/reject", response_model=ApprovalResponse)
async def reject_user(
    user_id: int,
    request: Request,
    permanent: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Reject a pending user.
    If permanent=True, deletes the user. Otherwise, sets is_active=False.
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already approved user. Use deactivate instead."
        )
    
    client_ip = request.client.host if request.client else None
    username = user.username
    
    if permanent:
        db.delete(user)
        db.commit()
        
        log_activity(
            db,
            current_user.id,
            ActivityType.DELETE_USER,
            f"Rejected and deleted pending user: {username}",
            ip_address=client_ip,
            metadata={"deleted_user_id": user_id, "username": username, "permanent": True}
        )
        
        return ApprovalResponse(
            status="rejected",
            message=f"User '{username}' has been permanently rejected and deleted.",
            user_id=user_id
        )
    else:
        user.is_active = False
        db.commit()
        
        log_activity(
            db,
            current_user.id,
            ActivityType.DELETE_USER,
            f"Rejected pending user: {username}",
            ip_address=client_ip,
            metadata={"rejected_user_id": user_id, "username": username, "permanent": False}
        )
        
        return ApprovalResponse(
            status="rejected",
            message=f"User '{username}' has been rejected and deactivated.",
            user_id=user.id
        )


@router.delete("/{user_id}", response_model=ApprovalResponse)
async def delete_pending_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Delete a pending user permanently.
    Alternative to POST /reject with permanent=true.
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an approved user via this endpoint. Use /api/admin/users/{id} instead."
        )
    
    username = user.username
    client_ip = request.client.host if request.client else None
    
    db.delete(user)
    db.commit()
    
    log_activity(
        db,
        current_user.id,
        ActivityType.DELETE_USER,
        f"Deleted pending user: {username}",
        ip_address=client_ip,
        metadata={"deleted_user_id": user_id, "username": username}
    )
    
    return ApprovalResponse(
        status="deleted",
        message=f"Pending user '{username}' has been deleted.",
        user_id=user_id
    )
