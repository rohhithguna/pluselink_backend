"""
User Settings Sync API
Endpoints for syncing user preferences across devices
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from database import get_db
from models import User
from auth import get_current_user
import json

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsData(BaseModel):
    theme: Optional[str] = "default"
    customThemes: Optional[Dict[str, Any]] = {}
    cursorGravity: Optional[bool] = True
    physicsStrength: Optional[str] = "medium"
    parallaxBackground: Optional[bool] = True
    animationSpeed: Optional[str] = "normal"
    hapticFeedback: Optional[bool] = False
    interfaceSounds: Optional[bool] = False
    soundStyle: Optional[str] = "glass"
    loginSound: Optional[bool] = True
    notificationVolume: Optional[float] = 0.5
    emergencyVisualMode: Optional[str] = "enhanced"
    notificationPopups: Optional[bool] = True
    urgentShake: Optional[bool] = True
    reactionAnimation: Optional[str] = "bounce"
    layoutMode: Optional[str] = "standard"
    splitViewEnabled: Optional[bool] = False
    autoCollapseSidebar: Optional[bool] = False
    spatialModeEnabled: Optional[bool] = False
    spatialMotionIntensity: Optional[str] = "full"
    spatialDepthBlur: Optional[float] = 0.5
    spatialParallax: Optional[bool] = True
    reducedEmergencyMotion: Optional[bool] = False
    silentEmergencyMode: Optional[bool] = False
    autoAcknowledgeOnOpen: Optional[bool] = False

class SettingsResponse(BaseModel):
    success: bool
    settings: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    last_synced: Optional[str] = None

@router.get("/sync", response_model=SettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch user's synced settings from server"""
    try:
        if current_user.settings_json:
            try:
                settings = json.loads(current_user.settings_json)
            except json.JSONDecodeError:
                settings = {}
        else:
            settings = {}
        
        return SettingsResponse(
            success=True,
            settings=settings,
            last_synced=str(current_user.created_at) if current_user.created_at else None
        )
    except Exception as e:
        return SettingsResponse(
            success=False,
            message=str(e)
        )

@router.post("/sync", response_model=SettingsResponse)
async def save_user_settings(
    settings_data: SettingsData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save user's settings to server for cross-device sync"""
    try:
        settings_dict = settings_data.dict()
        current_user.settings_json = json.dumps(settings_dict)
        db.commit()
        
        return SettingsResponse(
            success=True,
            settings=settings_dict,
            message="Settings synced successfully"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to sync settings: {str(e)}")

@router.delete("/sync", response_model=SettingsResponse)
async def reset_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset user's settings to defaults"""
    try:
        current_user.settings_json = None
        db.commit()
        
        return SettingsResponse(
            success=True,
            message="Settings reset to defaults"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


me_router = APIRouter(prefix="/api/me", tags=["me"])

@me_router.get("/settings", response_model=SettingsResponse)
async def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's settings (alias for /api/settings/sync)"""
    try:
        if current_user.settings_json:
            try:
                settings = json.loads(current_user.settings_json)
            except json.JSONDecodeError:
                settings = {}
        else:
            settings = {}
        
        return SettingsResponse(
            success=True,
            settings=settings
        )
    except Exception as e:
        return SettingsResponse(
            success=False,
            message=str(e)
        )

@me_router.put("/settings", response_model=SettingsResponse)
async def update_my_settings(
    settings_data: SettingsData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's settings (alias for POST /api/settings/sync)"""
    try:
        settings_dict = settings_data.dict()
        current_user.settings_json = json.dumps(settings_dict)
        db.commit()
        
        return SettingsResponse(
            success=True,
            settings=settings_dict,
            message="Settings saved successfully"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

