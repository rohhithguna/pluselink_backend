"""
Badge API Routes
Endpoints for user badge management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from models import User, UserBadge, UserRole
from auth import get_current_user, require_role
from services.badge_calculator import (
    get_user_badges, 
    calculate_all_badges,
    BADGE_INFO,
    BadgeType
)

router = APIRouter(prefix="/api/badges", tags=["badges"])


class BadgeResponse(BaseModel):
    type: str
    icon: str
    name: str
    description: str
    earned_at: str
    is_new: bool


class BadgeListResponse(BaseModel):
    badges: List[BadgeResponse]
    total: int


@router.get("/me", response_model=BadgeListResponse)
def get_my_badges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's badges"""
    calculate_all_badges(db, current_user.id)
    
    badges = get_user_badges(db, current_user.id)
    
    return BadgeListResponse(
        badges=badges,
        total=len(badges)
    )


@router.get("/user/{user_id}", response_model=BadgeListResponse)
def get_user_badges_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get badges for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    badges = get_user_badges(db, user_id)
    
    return BadgeListResponse(
        badges=badges,
        total=len(badges)
    )


@router.post("/mark-seen")
def mark_badges_seen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all current user's badges as seen (no longer new)"""
    db.query(UserBadge).filter(
        UserBadge.user_id == current_user.id,
        UserBadge.is_new == True
    ).update({"is_new": False})
    
    db.commit()
    
    return {"status": "success", "message": "All badges marked as seen"}


@router.post("/calculate")
def trigger_badge_calculation(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Admin-only: Trigger badge calculation for all users.
    This can be resource-intensive for large user bases.
    """
    users = db.query(User).all()
    total_new_badges = 0
    
    for user in users:
        newly_awarded = calculate_all_badges(db, user.id)
        total_new_badges += len(newly_awarded)
    
    return {
        "status": "success",
        "users_processed": len(users),
        "new_badges_awarded": total_new_badges
    }


@router.get("/types")
def get_all_badge_types():
    """Get all available badge types with their info"""
    result = []
    for badge_type, info in BADGE_INFO.items():
        result.append({
            "type": badge_type.value,
            "icon": info["icon"],
            "name": info["name"],
            "description": info["description"]
        })
    return result
