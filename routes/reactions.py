from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from pydantic import BaseModel
from database import get_db
from models import Reaction, Alert, User
from auth import get_current_user
from websocket_manager import ws_manager

router = APIRouter(prefix="/api/reactions", tags=["reactions"])

def get_reaction_counts_for_alert(db: Session, alert_id: int) -> dict:
    """Get reaction counts using SQL aggregation for better performance"""
    results = db.query(
        Reaction.emoji,
        func.count(Reaction.id).label('count')
    ).filter(
        Reaction.alert_id == alert_id
    ).group_by(Reaction.emoji).all()
    
    return {emoji: count for emoji, count in results}

class ReactionCreate(BaseModel):
    alert_id: int
    emoji: str

class ReactionResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    emoji: str
    username: str
    
    class Config:
        from_attributes = True

@router.post("", response_model=ReactionResponse)
async def add_reaction(
    reaction: ReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a reaction to an alert"""
    alert = db.query(Alert).filter(Alert.id == reaction.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    existing = db.query(Reaction).filter(
        Reaction.alert_id == reaction.alert_id,
        Reaction.user_id == current_user.id,
        Reaction.emoji == reaction.emoji
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already reacted with this emoji")
    
    new_reaction = Reaction(
        alert_id=reaction.alert_id,
        user_id=current_user.id,
        emoji=reaction.emoji
    )
    db.add(new_reaction)
    db.commit()
    db.refresh(new_reaction)
    
    reaction_counts = get_reaction_counts_for_alert(db, reaction.alert_id)
    
    await ws_manager.broadcast_reaction({
        "alert_id": reaction.alert_id,
        "reaction_counts": reaction_counts,
        "user_id": current_user.id,
        "emoji": reaction.emoji,
        "action": "add"
    })
    
    return ReactionResponse(
        id=new_reaction.id,
        alert_id=new_reaction.alert_id,
        user_id=new_reaction.user_id,
        emoji=new_reaction.emoji,
        username=current_user.username
    )

@router.delete("/{reaction_id}")
async def remove_reaction(
    reaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a reaction"""
    reaction = db.query(Reaction).filter(
        Reaction.id == reaction_id,
        Reaction.user_id == current_user.id
    ).first()
    
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")
    
    alert_id = reaction.alert_id
    emoji = reaction.emoji
    
    db.delete(reaction)
    db.commit()
    
    reaction_counts = get_reaction_counts_for_alert(db, alert_id)
    
    await ws_manager.broadcast_reaction({
        "alert_id": alert_id,
        "reaction_counts": reaction_counts,
        "user_id": current_user.id,
        "emoji": emoji,
        "action": "remove"
    })
    
    return {"status": "success"}

@router.get("/alert/{alert_id}")
def get_alert_reactions(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reactions for a specific alert"""
    reactions = db.query(Reaction).filter(Reaction.alert_id == alert_id).all()
    
    reaction_counts = {}
    user_reactions = []
    
    for reaction in reactions:
        if reaction.emoji not in reaction_counts:
            reaction_counts[reaction.emoji] = 0
        reaction_counts[reaction.emoji] += 1
        
        if reaction.user_id == current_user.id:
            user_reactions.append({
                "id": reaction.id,
                "emoji": reaction.emoji
            })
    
    return {
        "reaction_counts": reaction_counts,
        "user_reactions": user_reactions
    }
