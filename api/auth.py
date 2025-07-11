"""
Authentication API endpoints for the AI Studio application.
"""

import json
import os
from datetime import datetime
from urllib.parse import unquote
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from itsdangerous import BadSignature, URLSafeSerializer
from google.oauth2.credentials import Credentials

from database import User, get_db
from auth import create_user_session, delete_user_session, get_current_user, UserResponse
from config import CLIENT_SECRETS_FILE, SCOPES, GOOGLE_REDIRECT_URI, SECRET_KEY

# Allow insecure transport for local development
if os.getenv("ENVIRONMENT") != "production":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

router = APIRouter()
state_serializer = URLSafeSerializer(SECRET_KEY)

@router.post("/api/auth/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """Logout endpoint that clears the user session."""
    session_id = request.cookies.get("session_id")
    if session_id: 
        delete_user_session(db, session_id)
    response = Response(content='{"success": true}', media_type="application/json")
    response.delete_cookie(key="session_id")
    return response

@router.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        email=current_user.email, 
        full_name=current_user.full_name, 
        role=current_user.role
    )

@router.get("/api/classroom/auth-url")
async def get_google_auth_url(link_account: bool = False):
    """
    Get Google OAuth authorization URL.
    
    Args:
        link_account: If True, forces consent screen for account linking.
                     If False, uses standard login flow.
    """
    flow = Flow.from_client_config(
        client_config=CLIENT_SECRETS_FILE, 
        scopes=SCOPES, 
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    state_data = {
        "random": "some_random_state_string",
        "link_account": link_account
    }
    state = state_serializer.dumps(state_data)
    
    # Different flows for login vs account linking
    if link_account:
        # Force consent screen for account linking/re-linking
        authorization_url, _ = flow.authorization_url(
            access_type='offline', 
            include_granted_scopes='true', 
            state=state, 
            prompt='consent'
        )
    else:
        # Standard login flow - no forced consent
        authorization_url, _ = flow.authorization_url(
            access_type='offline', 
            include_granted_scopes='true', 
            state=state
        )
    
    return {"auth_url": authorization_url, "link_account": link_account}

@router.get("/api/classroom/auth-callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback and create user session."""
    state = request.query_params.get('state')
    try: 
        state_data = state_serializer.loads(state)
        # Handle both old format (string) and new format (dict)
        if isinstance(state_data, dict):
            link_account = state_data.get("link_account", False)
        else:
            # Legacy format - assume it's a login
            link_account = False
    except BadSignature: 
        return RedirectResponse("/auth/login.html?error=invalid_state")
    
    flow = Flow.from_client_config(
        client_config=CLIENT_SECRETS_FILE, 
        scopes=SCOPES, 
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    
    try: 
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as e:
        print(f"--- ERROR FETCHING GOOGLE TOKEN: {e} ---")
        return RedirectResponse(f"/auth/login.html?error=google_auth_failed")
    
    credentials = flow.credentials
    callback_scopes = unquote(request.query_params.get('scope', '')).split()
    
    # Get user info from Google
    user_info = build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()
    email = user_info.get('email')
    full_name = user_info.get('name', 'Google User')
    
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()
    
    if user and user.google_credentials and not link_account:
        # Existing user with credentials doing a regular login
        # Don't overwrite existing credentials, just create a session
        print(f"User {email} logging in with existing credentials")
        
        # Optionally update the access token if we got a new one
        if credentials.token:
            try:
                existing_creds = json.loads(user.google_credentials)
                existing_creds['token'] = credentials.token
                user.google_credentials = json.dumps(existing_creds)
                user.updated_at = datetime.utcnow()
                db.commit()
                print(f"Updated access token for user {email}")
            except Exception as e:
                print(f"Could not update access token: {e}")
    
    elif user and link_account:
        # Existing user explicitly linking/re-linking their account
        print(f"User {email} re-linking Google account")
        creds_dict = {
            'token': credentials.token, 
            'refresh_token': credentials.refresh_token, 
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id, 
            'client_secret': credentials.client_secret, 
            'scopes': callback_scopes
        }
        user.google_credentials = json.dumps(creds_dict)
        user.updated_at = datetime.utcnow()
        db.commit()
    
    elif user and not user.google_credentials:
        # Existing user without credentials (first time linking)
        print(f"User {email} linking Google account for the first time")
        creds_dict = {
            'token': credentials.token, 
            'refresh_token': credentials.refresh_token, 
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id, 
            'client_secret': credentials.client_secret, 
            'scopes': callback_scopes
        }
        user.google_credentials = json.dumps(creds_dict)
        user.updated_at = datetime.utcnow()
        db.commit()
    
    else:
        # New user - create account and link credentials
        print(f"Creating new user {email}")
        creds_dict = {
            'token': credentials.token, 
            'refresh_token': credentials.refresh_token, 
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id, 
            'client_secret': credentials.client_secret, 
            'scopes': callback_scopes
        }
        user = User(
            email=email,
            full_name=full_name,
            role="teacher",
            google_credentials=json.dumps(creds_dict)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create session and redirect
    session_id = create_user_session(db, user.id)
    
    # Choose redirect based on whether this was account linking
    if link_account:
        response = RedirectResponse("/profile.html?linked=true", status_code=307)
    else:
        response = RedirectResponse("/auth/callback.html", status_code=307)
    
    response.set_cookie(
        key="session_id", 
        value=session_id, 
        httponly=True, 
        max_age=7*24*60*60
    )
    return response

@router.get("/api/classroom/google-auth-check")
async def check_google_auth(current_user: User = Depends(get_current_user)):
    """Check if user has Google account linked."""
    if current_user.google_credentials: 
        return {"has_google_linked": True}
    auth_url_data = await get_google_auth_url(link_account=False)
    return {"has_google_linked": False, "auth_url": auth_url_data["auth_url"]}

@router.get("/api/classroom/link-account-url")
async def get_google_link_account_url(current_user: User = Depends(get_current_user)):
    """Get Google OAuth URL specifically for linking/re-linking account."""
    auth_url_data = await get_google_auth_url(link_account=True)
    return {
        "auth_url": auth_url_data["auth_url"],
        "message": "This will prompt for consent to link your Google account"
    }

@router.post("/api/classroom/unlink-account")
async def unlink_google_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Unlink Google account from user profile."""
    current_user.google_credentials = None
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    return {
        "message": "Google account unlinked successfully",
        "has_google_linked": False
    }

def validate_and_refresh_credentials(user: User, db: Session) -> bool:
    """
    Validate user's Google credentials and refresh if needed.
    Returns True if credentials are valid, False if they need to be re-linked.
    """
    if not user.google_credentials:
        return False
    
    try:
        creds_dict = json.loads(user.google_credentials)
        credentials = Credentials.from_authorized_user_info(info=creds_dict, scopes=SCOPES)
        
        # Check if credentials are expired and can be refreshed
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh()
                # Update stored credentials with new access token
                updated_creds = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': creds_dict.get('scopes', SCOPES)
                }
                user.google_credentials = json.dumps(updated_creds)
                user.updated_at = datetime.utcnow()
                db.commit()
                print(f"Refreshed credentials for user {user.email}")
                return True
            except Exception as e:
                print(f"Failed to refresh credentials for user {user.email}: {e}")
                return False
        
        elif credentials.valid:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error validating credentials for user {user.email}: {e}")
        return False

@router.get("/api/classroom/credentials-status")
async def check_credentials_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check the status of user's Google credentials."""
    if not current_user.google_credentials:
        return {
            "has_credentials": False,
            "valid": False,
            "message": "No Google account linked"
        }
    
    is_valid = validate_and_refresh_credentials(current_user, db)
    
    if is_valid:
        return {
            "has_credentials": True,
            "valid": True,
            "message": "Google credentials are valid"
        }
    else:
        return {
            "has_credentials": True,
            "valid": False,
            "message": "Google credentials are invalid or expired. Please re-link your account."
        }

@router.get("/api/debug/credentials")
async def debug_credentials(current_user: User = Depends(get_current_user)):
    """Debug endpoint to check credentials structure."""
    if not current_user.google_credentials:
        return {"error": "No credentials found"}
    
    try:
        creds_dict = json.loads(current_user.google_credentials)
        return {
            "user_email": current_user.email,
            "has_token": bool(creds_dict.get('token')),
            "has_refresh_token": bool(creds_dict.get('refresh_token')),
            "has_client_id": bool(creds_dict.get('client_id')),
            "has_client_secret": bool(creds_dict.get('client_secret')),
            "scopes": creds_dict.get('scopes', []),
            "token_uri": creds_dict.get('token_uri'),
            "expires_at": creds_dict.get('expires_at'),
            "credential_keys": list(creds_dict.keys())
        }
    except Exception as e:
        return {"error": f"Failed to parse credentials: {e}"}

@router.get("/api/debug/test-credentials")
async def test_credentials(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Test if credentials work by making a simple Google API call."""
    try:
        # Get the credentials
        credentials = validate_and_refresh_credentials(current_user, db)
        
        # Try to make a simple API call to test if credentials work
        from googleapiclient.discovery import build
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        
        return {
            "success": True,
            "user_info": {
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "verified_email": user_info.get("verified_email")
            },
            "credentials_valid": credentials.valid,
            "credentials_expired": credentials.expired
        }
    except HTTPException as e:
        return {
            "success": False,
            "error": e.detail,
            "status_code": e.status_code
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

@router.get("/api/debug/database")
async def debug_database(
    current_user = Depends(get_current_user)
):
    """Debug endpoint to check database contents"""
    from database import SessionLocal, Course, Assignment, Submission
    
    db = SessionLocal()
    try:
        # Get all courses
        courses = db.query(Course).all()
        assignments = db.query(Assignment).all()
        submissions = db.query(Submission).all()
        
        return {
            "courses": [{"id": str(c.id), "name": c.name, "google_course_id": c.google_course_id} for c in courses],
            "assignments": [{"id": str(a.id), "title": a.title, "google_assignment_id": a.google_assignment_id, "course_id": str(a.course_id)} for a in assignments],
            "submissions": [{"id": str(s.id), "google_submission_id": s.google_submission_id, "status": s.status} for s in submissions]
        }
    finally:
        db.close()
