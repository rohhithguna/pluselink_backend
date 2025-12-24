from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import UserPreferences, User
from auth import get_current_user

router = APIRouter(prefix="/api/preferences", tags=["preferences"])

class PreferencesUpdate(BaseModel):
    mute_emergency: bool = False
    mute_important: bool = False
    mute_info: bool = False
    mute_reminder: bool = False
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"

class PreferencesResponse(BaseModel):
    id: int
    user_id: int
    mute_emergency: bool
    mute_important: bool
    mute_info: bool
    mute_reminder: bool
    quiet_hours_enabled: bool
    quiet_hours_start: str
    quiet_hours_end: str
    
    class Config:
        from_attributes = True

@router.get("", response_model=PreferencesResponse)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's preferences"""
    preferences = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.id
    ).first()
    
    if not preferences:
        preferences = UserPreferences(user_id=current_user.id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    
    return preferences

@router.put("", response_model=PreferencesResponse)
def update_preferences(
    preferences_data: PreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update current user's preferences"""
    preferences = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.id
    ).first()
    
    if not preferences:
        preferences = UserPreferences(user_id=current_user.id)
        db.add(preferences)
    
    preferences.mute_emergency = preferences_data.mute_emergency
    preferences.mute_important = preferences_data.mute_important
    preferences.mute_info = preferences_data.mute_info
    preferences.mute_reminder = preferences_data.mute_reminder
    preferences.quiet_hours_enabled = preferences_data.quiet_hours_enabled
    preferences.quiet_hours_start = preferences_data.quiet_hours_start
    preferences.quiet_hours_end = preferences_data.quiet_hours_end
    
    db.commit()
    db.refresh(preferences)
    
    return preferences
