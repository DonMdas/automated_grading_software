from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User
from app.services.auth_service import AuthService
from app.services.google_classroom_service import GoogleClassroomService
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()
classroom_service = GoogleClassroomService()

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    username: str
    password: str
    full_name: str
    role: str = "teacher"

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=Token)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    
    # Check if user already exists
    if auth_service.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = auth_service.create_user(user_data.dict())
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    auth_service = AuthService(db)
    user = auth_service.get_current_user(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role
    }

# Dependency function for other modules
def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user for use in other modules"""
    auth_service = AuthService(db)
    user = auth_service.get_current_user(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.get("/google/signup")
async def google_signup_redirect():
    """Redirect to Google OAuth for signup"""
    try:
        auth_url = classroom_service.create_auth_url(state="signup")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Google signup: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate Google signup")

@router.get("/google/login")
async def google_login_redirect():
    """Redirect to Google OAuth for login"""
    try:
        auth_url = classroom_service.create_auth_url(state="login")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Google login: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate Google login")

@router.get("/google/callback")
async def google_auth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback for login/signup"""
    try:
        # Exchange code for tokens
        token_data = classroom_service.exchange_code_for_token(code, state)
        
        # Get user info from Google
        credentials = classroom_service.create_credentials_from_token(
            token_data['access_token'],
            token_data.get('refresh_token')
        )
        user_info = classroom_service.get_user_info(credentials)
        
        auth_service = AuthService(db)
        
        # Check if user exists
        existing_user = auth_service.get_user_by_email(user_info['email'])
        
        if state == "signup":
            if existing_user:
                # User already exists, redirect to login
                return RedirectResponse(url="/templates/auth/teacher_login.html?error=user_exists")
            
            # Create new user with Google info
            user_data = {
                "email": user_info['email'],
                "username": user_info['email'].split('@')[0],
                "password": None,  # Google authenticated users don't need password
                "full_name": user_info.get('name', ''),
                "role": "teacher",
                "google_id": user_info.get('id'),
                "google_access_token": token_data['access_token'],
                "google_refresh_token": token_data.get('refresh_token')
            }
            
            # Calculate token expiry
            expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
            user_data["google_token_expires_at"] = expires_at
            
            user = auth_service.create_google_user(user_data)
            access_token = auth_service.create_access_token(data={"sub": user.email})
            
            # Redirect to dashboard with token
            return RedirectResponse(url=f"/dashboard?token={access_token}&google_connected=true")
            
        elif state == "login":
            if not existing_user:
                # User doesn't exist, redirect to signup
                return RedirectResponse(url="/templates/auth/teacher_signup.html?error=user_not_found")
            
            # Update existing user with Google tokens
            expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            existing_user.google_id = user_info.get('id')
            existing_user.google_access_token = token_data['access_token']
            existing_user.google_refresh_token = token_data.get('refresh_token')
            existing_user.google_token_expires_at = expires_at
            
            db.commit()
            
            access_token = auth_service.create_access_token(data={"sub": existing_user.email})
            
            # Redirect to dashboard with token
            return RedirectResponse(url=f"/dashboard?token={access_token}&google_connected=true")
        
        else:
            # Invalid state
            return RedirectResponse(url="/templates/auth/teacher_login.html?error=invalid_state")
            
    except Exception as e:
        logger.error(f"Error in Google auth callback: {e}")
        return RedirectResponse(url="/templates/auth/teacher_login.html?error=auth_failed")
