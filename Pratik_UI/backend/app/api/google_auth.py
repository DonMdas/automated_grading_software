"""
Google OAuth endpoints for the AI Grading Platform
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

# Configuration
from app.core.config import settings
from app.services.auth_service import auth_service
from app.db.connector import get_postgres_session

logger = logging.getLogger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/api/auth", tags=["authentication"])

@router.get("/google")
async def google_oauth():
    """Initiate Google OAuth flow"""
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Create flow instance
        # Request all the scopes that Google Classroom integration needs
        flow = Flow.from_client_secrets_file(
            'client_secrets.json',
            scopes=[
                'openid',
                'email', 
                'profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/classroom.courses.readonly',
                'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
                'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
                'https://www.googleapis.com/auth/classroom.rosters.readonly'
            ]
        )
        
        # Set redirect URI (must match what's configured in Google Console)
        flow.redirect_uri = 'http://localhost:8001'
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        logger.info("🔗 Initiating Google OAuth flow")
        return {"authorization_url": authorization_url, "state": state}
        
    except Exception as e:
        logger.error(f"❌ Google OAuth error: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth setup failed: {str(e)}")

@router.get("/google/callback")
async def google_oauth_callback(code: str, state: str = None):
    """Handle Google OAuth callback"""
    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        
        # Create flow for token exchange with the same scopes
        flow = Flow.from_client_secrets_file(
            'client_secrets.json',
            scopes=[
                'openid',
                'email', 
                'profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/classroom.courses.readonly',
                'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
                'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
                'https://www.googleapis.com/auth/classroom.rosters.readonly'
            ]
        )
        flow.redirect_uri = 'http://localhost:8001'
        
        # Exchange code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user info
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        
        # Store or update user in database
        with get_postgres_session() as session:
            auth_service.set_db(session)
            user = auth_service.get_user_by_email(user_info['email'])
            
            if not user:
                # Create new Google user
                user_data = {
                    "email": user_info['email'],
                    "username": user_info['email'].split('@')[0],
                    "full_name": user_info.get('name', user_info['email']),
                    "role": "teacher",
                    "google_id": user_info['id'],
                    "google_access_token": credentials.token,
                    "google_refresh_token": credentials.refresh_token,
                    "google_token_expires_at": credentials.expiry
                }
                user = auth_service.create_google_user(user_data)
            else:
                # Update existing user's tokens
                user.google_access_token = credentials.token
                user.google_refresh_token = credentials.refresh_token
                user.google_token_expires_at = credentials.expiry
                session.commit()
        
        # Create JWT token
        access_token = auth_service.create_access_token(
            data={"sub": user.email}
        )
        
        # Redirect to frontend with token
        return RedirectResponse(
            url=f"http://localhost:3002/auth/google-success.html?token={access_token}&email={user.email}&name={user.full_name}"
        )
        
    except Exception as e:
        logger.error(f"❌ Google OAuth callback error: {e}")
        return RedirectResponse(
            url=f"http://localhost:3002/auth/google-error.html?error={str(e)}"
        )
