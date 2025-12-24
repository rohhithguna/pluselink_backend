from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from datetime import datetime
import json
import os

from database import get_db, init_db, SessionLocal
from models import User, UserRole, ActivityLog, ActivityType
from auth import verify_password, create_access_token, get_password_hash, decode_access_token
from websocket_manager import ws_manager
from routes import alerts, reactions, analytics, users, acknowledgments, preferences, templates, badges, timeline, settings_sync
from routes import admin_users, admin_analytics, pending_users

app = FastAPI(title="PulseLink API", version="2.0.0", redirect_slashes=False)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()
    print("Database initialized")
    
    # Auto-create admin user if none exists
    db = SessionLocal()
    try:
        from auth import get_password_hash
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                email="admin@pulselink.com",
                full_name="System Administrator",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                is_approved=True,
                first_login=False,
                created_at=datetime.utcnow()
            )
            db.add(admin)
            db.commit()
            print("✅ Default admin user created (username: admin, password: admin123)")
    except Exception as e:
        print(f"Admin creation check: {e}")
    finally:
        db.close()

app.include_router(alerts.router)
app.include_router(reactions.router)
app.include_router(analytics.router)
app.include_router(users.router)
app.include_router(acknowledgments.router)
app.include_router(preferences.router)
app.include_router(templates.router)
app.include_router(badges.router)
app.include_router(timeline.router)
app.include_router(settings_sync.router)
app.include_router(settings_sync.me_router)

app.include_router(admin_users.router)
app.include_router(admin_analytics.router)
app.include_router(pending_users.router)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict
    first_login: bool


class SignupRequest(BaseModel):
    full_name: str
    username: str
    password: str
    role: str
    gender: str = None
    email: str = None
    phone: str = None

class SignupResponse(BaseModel):
    status: str
    message: str

@app.post("/api/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginRequest, db: Session = Depends(get_db)):
    """Login endpoint with activity logging and approval check"""
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if hasattr(user, 'is_active') and user.is_active is False:
        raise HTTPException(status_code=401, detail="Account is deactivated. Contact administrator.")
    
    if hasattr(user, 'is_approved') and user.is_approved is False:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "pending_approval",
                "message": "Your account is created but still awaiting admin approval."
            }
        )
    
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user.last_login_at = datetime.utcnow()
    
    is_first_login = user.first_login if hasattr(user, 'first_login') and user.first_login is not None else True
    
    db.commit()
    
    try:
        client_ip = request.client.host if request.client else None
        log = ActivityLog(
            user_id=user.id,
            activity_type=ActivityType.LOGIN,
            description=f"User {user.username} logged in",
            ip_address=client_ip,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Activity log error: {e}")
    
    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value
    }
    access_token = create_access_token(token_data)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name or user.username,
            "department": getattr(user, 'department', None),
            "year": getattr(user, 'year', None),
            "section": getattr(user, 'section', None),
            "phone": getattr(user, 'phone', None),
            "is_active": getattr(user, 'is_active', True),
            "first_login": is_first_login
        },
        first_login=is_first_login
    )


@app.post("/api/auth/signup", response_model=SignupResponse, status_code=201)
@limiter.limit("3/minute")
async def signup(request: Request, signup_data: SignupRequest, db: Session = Depends(get_db)):
    """
    Signup endpoint for new faculty and student users.
    Creates user with is_approved=False, requiring admin approval.
    """
    allowed_roles = ["faculty", "student"]
    if signup_data.role.lower() not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Self-signup is only allowed for: {', '.join(allowed_roles)}"
        )
    
    try:
        role = UserRole(signup_data.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {signup_data.role}"
        )
    
    if db.query(User).filter(User.username == signup_data.username).first():
        raise HTTPException(
            status_code=400,
            detail="Username already exists. Please choose a different username."
        )
    
    if signup_data.email:
        if db.query(User).filter(User.email == signup_data.email).first():
            raise HTTPException(
                status_code=400,
                detail="Email already registered. Please use a different email."
            )
    
    new_user = User(
        full_name=signup_data.full_name,
        username=signup_data.username,
        password_hash=get_password_hash(signup_data.password),
        role=role,
        gender=signup_data.gender,
        email=signup_data.email or "",
        phone=signup_data.phone,
        is_active=True,
        is_approved=False,
        first_login=True,
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    try:
        client_ip = request.client.host if request.client else None
        log = ActivityLog(
            user_id=new_user.id,
            activity_type=ActivityType.CREATE_USER,
            description=f"New {signup_data.role} signup: {signup_data.username} (pending approval)",
            ip_address=client_ip,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Activity log error: {e}")
    
    return SignupResponse(
        status="pending_approval",
        message="Your account has been created and is awaiting approval by the administrator. You will be able to login once approved."
    )

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: str = None):
    """WebSocket endpoint for real-time updates"""
    if not token:
        await websocket.close(code=1008, reason="No token provided")
        return
    
    try:
        token_data = decode_access_token(token)
        if token_data.user_id != user_id:
            await websocket.close(code=1008, reason="Token user_id mismatch")
            return
    except:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        if hasattr(user, 'is_active') and user.is_active is False:
            await websocket.close(code=1008, reason="Account deactivated")
            return
        
        user_role = user.role.value
    finally:
        db.close()
    
    await ws_manager.connect(websocket, user_id, user_role)
    
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong", "message": "Connection alive"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)

@app.get("/")
async def root():
    return {
        "message": "PulseLink API",
        "version": "2.0.0",
        "status": "running"
    }

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "active_connections": ws_manager.get_active_users_count()
    }
