"""
User Profile API Routes
Handles current user profile fetching and editing
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json

from database import get_db
from models import User, UserRole, ActivityLog, ActivityType
from auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str]
    department: Optional[str]
    year: Optional[str]
    section: Optional[str]
    phone: Optional[str]
    is_active: bool
    first_login: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    """Fields that users can update on their own profile"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    section: Optional[str] = None
    phone: Optional[str] = None


class OnboardingComplete(BaseModel):
    """Request to complete first-login onboarding"""
    theme: Optional[str] = None
    sound_enabled: Optional[bool] = True


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


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user's full profile information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        full_name=current_user.full_name or current_user.username,
        department=current_user.department,
        year=current_user.year,
        section=current_user.section,
        phone=current_user.phone,
        is_active=current_user.is_active if current_user.is_active is not None else True,
        first_login=current_user.first_login if current_user.first_login is not None else True,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.put("/me", response_model=UserResponse)
def update_current_user_profile(
    request: Request,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update current user's profile.
    Users can update: email, full_name, department, year, section, phone.
    Users cannot update: username, role, is_active.
    """
    if profile_data.email is not None:
        existing = db.query(User).filter(
            User.email == profile_data.email,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = profile_data.email
    
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
    
    if profile_data.department is not None:
        current_user.department = profile_data.department
    
    if profile_data.year is not None:
        current_user.year = profile_data.year
    
    if profile_data.section is not None:
        current_user.section = profile_data.section
    
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    
    db.commit()
    db.refresh(current_user)
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.UPDATE_PROFILE,
        f"Updated profile",
        ip_address=client_ip
    )
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        full_name=current_user.full_name or current_user.username,
        department=current_user.department,
        year=current_user.year,
        section=current_user.section,
        phone=current_user.phone,
        is_active=current_user.is_active if current_user.is_active is not None else True,
        first_login=current_user.first_login if current_user.first_login is not None else True,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.post("/me/complete-onboarding")
def complete_onboarding(
    onboarding_data: OnboardingComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark onboarding as complete for the current user.
    Called after first-login modal is completed.
    """
    current_user.first_login = False
    
    if onboarding_data.theme or onboarding_data.sound_enabled is not None:
        settings = {}
        try:
            if current_user.settings_json:
                settings = json.loads(current_user.settings_json)
        except:
            settings = {}
        
        if onboarding_data.theme:
            settings["theme"] = onboarding_data.theme
        if onboarding_data.sound_enabled is not None:
            settings["soundEnabled"] = onboarding_data.sound_enabled
        
        current_user.settings_json = json.dumps(settings)
    
    db.commit()
    
    return {"message": "Onboarding completed", "first_login": False}


@router.get("/", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all users (for internal features like alert targeting)"""
    users = db.query(User).filter(User.is_active == True).all()
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role.value,
            full_name=user.full_name or user.username,
            department=user.department,
            year=user.year,
            section=user.section,
            phone=user.phone,
            is_active=user.is_active if user.is_active is not None else True,
            first_login=user.first_login if user.first_login is not None else True,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        )
        for user in users
    ]
