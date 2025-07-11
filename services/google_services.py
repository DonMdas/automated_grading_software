"""
Google Services utilities for the AI Studio application.
"""

import json
from fastapi import Depends, HTTPException
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from sqlalchemy.orm import Session

from auth import get_current_user
from database import User, get_db
from config import SCOPES

def validate_and_refresh_credentials(user: User, db: Session) -> Credentials:
    """
    Validate user's Google credentials and refresh if needed.
    Returns valid credentials or raises HTTPException.
    """
    if not user.google_credentials:
        raise HTTPException(
            status_code=403, 
            detail="No Google account linked. Please link your Google account first."
        )
    
    try:
        creds_dict = json.loads(user.google_credentials)
        print(f"DEBUG: Credential keys for user {user.email}: {list(creds_dict.keys())}")
        print(f"DEBUG: Has refresh_token: {bool(creds_dict.get('refresh_token'))}")
        print(f"DEBUG: Token URI: {creds_dict.get('token_uri')}")
        
        credentials = Credentials.from_authorized_user_info(info=creds_dict, scopes=SCOPES)
        print(f"DEBUG: Credentials created successfully")
        print(f"DEBUG: Credentials expired: {credentials.expired}")
        print(f"DEBUG: Credentials valid: {credentials.valid}")
        
        # Always try to refresh if we have a refresh token and credentials are not valid
        if credentials.refresh_token and (credentials.expired or not credentials.valid):
            print(f"DEBUG: Attempting to refresh credentials for user {user.email}")
            try:
                request = Request()
                credentials.refresh(request)
                print(f"DEBUG: Credentials refreshed successfully")
                
                # Update stored credentials with new access token
                updated_creds = {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': creds_dict.get('scopes', SCOPES),
                    'expiry': credentials.expiry.isoformat() if credentials.expiry else None
                }
                user.google_credentials = json.dumps(updated_creds)
                db.commit()
                print(f"Successfully refreshed and updated credentials for user {user.email}")
                
                return credentials
                
            except Exception as e:
                print(f"Failed to refresh credentials for user {user.email}: {e}")
                print(f"DEBUG: Error type: {type(e).__name__}")
                raise HTTPException(
                    status_code=403,
                    detail="Google credentials expired and could not be refreshed. Please re-link your Google account."
                )
        
        # Check if credentials are valid without refresh
        if credentials.valid:
            print(f"DEBUG: Credentials are valid for user {user.email}")
            return credentials
        else:
            print(f"DEBUG: Credentials are not valid and no refresh token available")
            raise HTTPException(
                status_code=403,
                detail="Invalid Google credentials. Please re-link your Google account."
            )
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error for user {user.email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Corrupted Google credentials. Please re-link your Google account."
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error validating credentials for user {user.email}: {e}")
        print(f"DEBUG: Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error validating Google credentials: {e}"
        )

async def get_classroom_service(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get Google Classroom service for the current user."""
    try:
        credentials = validate_and_refresh_credentials(current_user, db)
        return build('classroom', 'v1', credentials=credentials)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not create Classroom service: {e}"
        )

async def get_drive_service(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get Google Drive service for the current user."""
    try:
        credentials = validate_and_refresh_credentials(current_user, db)
        return build('drive', 'v3', credentials=credentials)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Could not create Drive service: {e}"
        )
