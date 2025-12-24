"""
Admin User Management API Routes
Only accessible by super_admin role
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import json

from database import get_db
from models import User, UserRole, ActivityLog, ActivityType
from auth import get_current_user, get_password_hash, require_role

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


class UserCreate(BaseModel):
    username: str
    password: str
    confirm_password: str
    email: str
    role: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    section: Optional[str] = None
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[str] = None
    section: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class PasswordReset(BaseModel):
    new_password: str
    confirm_password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    full_name: Optional[str]
    department: Optional[str]
    year: Optional[str]
    section: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    is_active: bool
    is_approved: bool
    first_login: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


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


def validate_role(role: str) -> UserRole:
    """Validate and convert string to UserRole enum"""
    try:
        return UserRole(role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Must be one of: super_admin, college_admin, faculty, student"
        )


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    List all users with optional filtering.
    Only accessible by super_admin.
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == validate_role(role))
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.full_name.ilike(search_term))
        )
    
    query = query.order_by(User.created_at.desc())
    
    users = query.offset(skip).limit(limit).all()
    
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role.value,
            full_name=u.full_name,
            department=u.department,
            year=u.year,
            section=u.section,
            phone=u.phone,
            gender=getattr(u, 'gender', None),
            is_active=u.is_active if u.is_active is not None else True,
            is_approved=getattr(u, 'is_approved', True),
            first_login=u.first_login if u.first_login is not None else True,
            created_at=u.created_at,
            last_login_at=u.last_login_at
        )
        for u in users
    ]


@router.get("/stats")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Get user statistics for control center.
    """
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    
    role_counts = {}
    for role in UserRole:
        count = db.query(func.count(User.id)).filter(User.role == role).scalar()
        role_counts[role.value] = count
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "users_by_role": role_counts
    }


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Create a new user.
    Only accessible by super_admin.
    """
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    role = validate_role(user_data.role)
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        role=role,
        full_name=user_data.full_name,
        department=user_data.department,
        year=user_data.year,
        section=user_data.section,
        phone=user_data.phone,
        is_active=True,
        is_approved=True,
        first_login=True,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.CREATE_USER,
        f"Created user: {new_user.username} with role {new_user.role.value}",
        ip_address=client_ip,
        metadata={"created_user_id": new_user.id, "role": new_user.role.value}
    )
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role.value,
        full_name=new_user.full_name,
        department=new_user.department,
        year=new_user.year,
        section=new_user.section,
        phone=new_user.phone,
        gender=getattr(new_user, 'gender', None),
        is_active=new_user.is_active,
        is_approved=getattr(new_user, 'is_approved', True),
        first_login=new_user.first_login,
        created_at=new_user.created_at,
        last_login_at=new_user.last_login_at
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: Request,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Update a user's information.
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user_data.email is not None:
        existing = db.query(User).filter(User.email == user_data.email, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = user_data.email
    
    if user_data.role is not None:
        user.role = validate_role(user_data.role)
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.department is not None:
        user.department = user_data.department
    
    if user_data.year is not None:
        user.year = user_data.year
    
    if user_data.section is not None:
        user.section = user_data.section
    
    if user_data.phone is not None:
        user.phone = user_data.phone
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    db.commit()
    db.refresh(user)
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.UPDATE_USER,
        f"Updated user: {user.username}",
        ip_address=client_ip,
        metadata={"updated_user_id": user.id}
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        full_name=user.full_name,
        department=user.department,
        year=user.year,
        section=user.section,
        phone=user.phone,
        gender=getattr(user, 'gender', None),
        is_active=user.is_active if user.is_active is not None else True,
        is_approved=getattr(user, 'is_approved', True),
        first_login=user.first_login if user.first_login is not None else True,
        created_at=user.created_at,
        last_login_at=user.last_login_at
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    permanent: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Delete or deactivate a user.
    Set permanent=true for hard delete, otherwise soft delete (deactivate).
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    client_ip = request.client.host if request.client else None
    
    if permanent:
        username = user.username
        db.delete(user)
        db.commit()
        
        log_activity(
            db,
            current_user.id,
            ActivityType.DELETE_USER,
            f"Permanently deleted user: {username}",
            ip_address=client_ip,
            metadata={"deleted_user_id": user_id, "permanent": True}
        )
        
        return {"message": f"User {username} permanently deleted"}
    else:
        user.is_active = False
        db.commit()
        
        log_activity(
            db,
            current_user.id,
            ActivityType.DELETE_USER,
            f"Deactivated user: {user.username}",
            ip_address=client_ip,
            metadata={"deleted_user_id": user_id, "permanent": False}
        )
        
        return {"message": f"User {user.username} deactivated"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Reactivate a deactivated user.
    Only accessible by super_admin.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    db.commit()
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.UPDATE_USER,
        f"Reactivated user: {user.username}",
        ip_address=client_ip,
        metadata={"activated_user_id": user_id}
    )
    
    return {"message": f"User {user.username} reactivated"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    password_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN))
):
    """
    Reset a user's password.
    Only accessible by super_admin.
    """
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.password_hash = get_password_hash(password_data.new_password)
    user.first_login = True
    db.commit()
    
    client_ip = request.client.host if request.client else None
    log_activity(
        db,
        current_user.id,
        ActivityType.RESET_PASSWORD,
        f"Reset password for user: {user.username}",
        ip_address=client_ip,
        metadata={"reset_user_id": user_id}
    )
    
    return {"message": f"Password reset for user {user.username}"}
