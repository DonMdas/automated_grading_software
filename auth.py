"""
Authentication utilities and models for the AI Studio application.
"""

import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import User, UserSession, get_db
from config import SESSION_EXPIRE_DAYS

class UserResponse(BaseModel):
    email: str
    full_name: str
    role: str

def create_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)

def create_user_session(db: Session, user_id: uuid.UUID) -> str:
    """Create a new user session and return the session ID."""
    session_id = create_session_token()
    expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRE_DAYS)
    db_session = UserSession(session_id=session_id, user_id=user_id, expires_at=expires_at)
    db.add(db_session)
    db.commit()
    return session_id

def get_user_from_session(db: Session, session_id: str) -> Optional[User]:
    """Get user from session ID, cleaning up expired sessions."""
    # Clean up expired sessions
    db.query(UserSession).filter(UserSession.expires_at < datetime.utcnow()).delete()
    db.commit()
    
    # Get active session
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id, 
        UserSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session: 
        return None
    
    return db.query(User).filter(User.id == session.user_id).first()

def delete_user_session(db: Session, session_id: str):
    """Delete a user session."""
    db.query(UserSession).filter(UserSession.session_id == session_id).delete()
    db.commit()

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency to get the current authenticated user."""
    session_id = request.cookies.get("session_id")
    if not session_id: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Not authenticated"
        )
    
    user = get_user_from_session(db, session_id)
    if not user: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or expired session"
        )
    
    return user
