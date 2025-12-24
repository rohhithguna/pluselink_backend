from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database import get_db
from models import AlertTemplate, User, UserRole, AlertPriority, AlertCategory
from auth import get_current_user, require_role

router = APIRouter(prefix="/api/templates", tags=["templates"])

class TemplateCreate(BaseModel):
    name: str
    title: str
    message: str
    priority: AlertPriority
    category: AlertCategory

class TemplateUpdate(BaseModel):
    name: str = None
    title: str = None
    message: str = None
    priority: AlertPriority = None
    category: AlertCategory = None
    is_active: bool = None

class TemplateResponse(BaseModel):
    id: int
    name: str
    title: str
    message: str
    priority: str
    category: str
    created_by_id: int
    created_by_name: str
    created_at: str
    is_active: bool
    
    class Config:
        from_attributes = True

@router.post("", response_model=TemplateResponse)
def create_template(
    template: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN, UserRole.FACULTY))
):
    """Create a new alert template"""
    new_template = AlertTemplate(
        name=template.name,
        title=template.title,
        message=template.message,
        priority=template.priority,
        category=template.category,
        created_by_id=current_user.id
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return TemplateResponse(
        id=new_template.id,
        name=new_template.name,
        title=new_template.title,
        message=new_template.message,
        priority=new_template.priority.value,
        category=new_template.category.value,
        created_by_id=new_template.created_by_id,
        created_by_name=current_user.full_name or current_user.username,
        created_at=new_template.created_at.isoformat(),
        is_active=new_template.is_active
    )

@router.get("", response_model=List[TemplateResponse])
def get_templates(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all active templates"""
    templates = db.query(AlertTemplate).filter(
        AlertTemplate.is_active == True
    ).order_by(AlertTemplate.created_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    for template in templates:
        creator = db.query(User).filter(User.id == template.created_by_id).first()
        result.append(TemplateResponse(
            id=template.id,
            name=template.name,
            title=template.title,
            message=template.message,
            priority=template.priority.value,
            category=template.category.value,
            created_by_id=template.created_by_id,
            created_by_name=creator.full_name if creator else "Unknown",
            created_at=template.created_at.isoformat(),
            is_active=template.is_active
        ))
    
    return result

@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific template"""
    template = db.query(AlertTemplate).filter(AlertTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    creator = db.query(User).filter(User.id == template.created_by_id).first()
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        title=template.title,
        message=template.message,
        priority=template.priority.value,
        category=template.category.value,
        created_by_id=template.created_by_id,
        created_by_name=creator.full_name if creator else "Unknown",
        created_at=template.created_at.isoformat(),
        is_active=template.is_active
    )

@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN, UserRole.FACULTY))
):
    """Update a template"""
    template = db.query(AlertTemplate).filter(AlertTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.created_by_id != current_user.id and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized to update this template")
    
    if template_data.name is not None:
        template.name = template_data.name
    if template_data.title is not None:
        template.title = template_data.title
    if template_data.message is not None:
        template.message = template_data.message
    if template_data.priority is not None:
        template.priority = template_data.priority
    if template_data.category is not None:
        template.category = template_data.category
    if template_data.is_active is not None:
        template.is_active = template_data.is_active
    
    db.commit()
    db.refresh(template)
    
    creator = db.query(User).filter(User.id == template.created_by_id).first()
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        title=template.title,
        message=template.message,
        priority=template.priority.value,
        category=template.category.value,
        created_by_id=template.created_by_id,
        created_by_name=creator.full_name if creator else "Unknown",
        created_at=template.created_at.isoformat(),
        is_active=template.is_active
    )

@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.COLLEGE_ADMIN))
):
    """Delete a template (admin only)"""
    template = db.query(AlertTemplate).filter(AlertTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.is_active = False
    db.commit()
    
    return {"status": "success"}
