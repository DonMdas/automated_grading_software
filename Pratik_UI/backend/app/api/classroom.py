from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.api.auth import get_current_user_dependency as get_current_user
from app.models.models import User
from app.db.database import get_db
from app.services.google_classroom_service import GoogleClassroomService
from app.core.config import Settings
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import json

router = APIRouter()
settings = Settings()
logger = logging.getLogger(__name__)

# Initialize Google Classroom Service
classroom_service = GoogleClassroomService()

@router.get("/auth")
async def initiate_google_auth(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Initiate Google OAuth flow for classroom integration"""
    try:
        # Create state parameter with user info for security
        state = f"user_{current_user.id}"
        auth_url = classroom_service.create_auth_url(state=state)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Google auth: {e}")
        raise HTTPException(status_code=500, detail="Failed to initiate Google authentication")

@router.get("/auth/callback")
async def google_auth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback and store tokens"""
    try:
        # Extract user ID from state
        if not state.startswith("user_"):
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        user_id = int(state.replace("user_", ""))
        
        # Exchange code for tokens
        token_data = classroom_service.exchange_code_for_token(code, state)
        
        # Get user info from Google
        credentials = classroom_service.create_credentials_from_token(
            token_data['access_token'],
            token_data.get('refresh_token')
        )
        user_info = classroom_service.get_user_info(credentials)
        
        # Update user with Google credentials
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate token expiry
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 3600))
        
        # Update user with Google tokens
        user.google_id = user_info.get('id')
        user.google_access_token = token_data['access_token']
        user.google_refresh_token = token_data.get('refresh_token')
        user.google_token_expires_at = expires_at
        
        db.commit()
        
        # Redirect to classroom page with success
        return RedirectResponse(url="/classroom?connected=true")
        
    except Exception as e:
        logger.error(f"Error in Google auth callback: {e}")
        return RedirectResponse(url="/classroom?error=auth_failed")

@router.get("/status")
async def get_connection_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Google Classroom connection status"""
    # Refresh user data from database
    user = db.query(User).filter(User.id == current_user.id).first()
    
    connected = bool(
        user.google_access_token and 
        user.google_token_expires_at and 
        user.google_token_expires_at > datetime.utcnow()
    )
    
    return {
        "connected": connected,
        "userEmail": user.email,
        "lastSync": user.updated_at.isoformat() if user.updated_at else None,
        "googleId": user.google_id
    }

@router.post("/disconnect")
async def disconnect_google_classroom(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect from Google Classroom"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        # Clear Google credentials
        user.google_id = None
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_token_expires_at = None
        
        db.commit()
        
        return {"message": "Successfully disconnected from Google Classroom"}
    except Exception as e:
        logger.error(f"Error disconnecting from Google: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect")

@router.get("/courses")
async def get_classroom_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Google Classroom courses for the authenticated user"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        # Check if user has valid tokens
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        # Check if token is expired and refresh if needed
        if user.google_token_expires_at <= datetime.utcnow():
            if not user.google_refresh_token:
                raise HTTPException(status_code=401, detail="Token expired and no refresh token available")
            
            # Refresh the token
            new_credentials = classroom_service.refresh_credentials(user.google_refresh_token)
            user.google_access_token = new_credentials.token
            user.google_token_expires_at = new_credentials.expiry
            db.commit()
        
        # Create credentials object
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        # Get courses
        courses = classroom_service.get_courses(credentials)
        return {"courses": courses}
        
    except Exception as e:
        logger.error(f"Error getting courses: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/courses/{course_id}/coursework")
async def get_course_coursework(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get coursework for a specific course"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        coursework = classroom_service.get_course_work(credentials, course_id)
        return {"coursework": coursework}
        
    except Exception as e:
        logger.error(f"Error getting coursework: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/courses/{course_id}/students")
async def get_course_students(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get students for a specific course"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        students = classroom_service.get_students(credentials, course_id)
        return {"students": students}
        
    except Exception as e:
        logger.error(f"Error getting students: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/courses/{course_id}/coursework/{coursework_id}/submissions")
async def get_coursework_submissions(
    course_id: str,
    coursework_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get submissions for a specific coursework"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        submissions = classroom_service.get_submissions(credentials, course_id, coursework_id)
        return {"submissions": submissions}
        
    except Exception as e:
        logger.error(f"Error getting submissions: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/import-assignment")
async def import_classroom_assignment(
    assignment_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import an assignment from Google Classroom"""
    try:
        from app.models.models import Assignment, Submission
        
        user = db.query(User).filter(User.id == current_user.id).first()
        
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        course_id = assignment_data.get('courseId')
        coursework_id = assignment_data.get('courseworkId')
        
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        # Get coursework details
        coursework_list = classroom_service.get_course_work(credentials, course_id)
        coursework = next((cw for cw in coursework_list if cw['id'] == coursework_id), None)
        
        if not coursework:
            raise HTTPException(status_code=404, detail="Coursework not found")
        
        # Create assignment in our database
        assignment = Assignment(
            title=coursework['title'],
            description=coursework.get('description', ''),
            teacher_id=current_user.id,
            classroom_id=coursework_id,
            max_score=coursework.get('maxPoints', 100.0)
        )
        
        db.add(assignment)
        db.flush()  # Get the assignment ID
        
        # Get and import submissions if requested
        submissions_imported = 0
        if assignment_data.get('importSubmissions', False):
            submissions = classroom_service.get_submissions(credentials, course_id, coursework_id)
            students = classroom_service.get_students(credentials, course_id)
            
            # Create a student lookup dict
            student_lookup = {s['user_id']: s['profile'] for s in students}
            
            for sub in submissions:
                if sub['state'] == 'TURNED_IN':
                    student = student_lookup.get(sub['user_id'], {})
                    
                    submission = Submission(
                        assignment_id=assignment.id,
                        student_email=student.get('email', ''),
                        student_name=student.get('name', ''),
                        status='imported'
                    )
                    
                    db.add(submission)
                    submissions_imported += 1
        
        db.commit()
        
        return {
            "message": "Assignment imported successfully",
            "assignment_id": assignment.id,
            "coursework_id": coursework_id,
            "submissions_imported": submissions_imported
        }
        
    except Exception as e:
        logger.error(f"Error importing assignment: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Additional endpoints for frontend integration
@router.get("/classes")
async def get_classes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Google Classroom classes (alias for courses)"""
    return await get_classroom_courses(current_user, db)

@router.get("/assignments")
async def get_all_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all assignments from all courses"""
    try:
        user = db.query(User).filter(User.id == current_user.id).first()
        
        if not user.google_access_token:
            raise HTTPException(status_code=401, detail="Not connected to Google Classroom")
        
        credentials = classroom_service.create_credentials_from_token(
            user.google_access_token,
            user.google_refresh_token
        )
        
        # Get all courses
        courses = classroom_service.get_courses(credentials)
        all_assignments = []
        
        for course in courses:
            try:
                coursework = classroom_service.get_course_work(credentials, course['id'])
                for work in coursework:
                    work['courseName'] = course['name']
                    work['courseId'] = course['id']
                    all_assignments.append(work)
            except Exception as e:
                logger.warning(f"Could not get coursework for course {course['id']}: {e}")
                continue
        
        return {"assignments": all_assignments}
        
    except Exception as e:
        logger.error(f"Error getting all assignments: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/assignments/recent")
async def get_recent_assignments(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent assignments from Google Classroom"""
    try:
        all_assignments_response = await get_all_assignments(current_user, db)
        assignments = all_assignments_response["assignments"]
        
        # Sort by creation time and limit
        sorted_assignments = sorted(
            assignments, 
            key=lambda x: x.get('creationTime', ''), 
            reverse=True
        )[:limit]
        
        return sorted_assignments
        
    except Exception as e:
        logger.error(f"Error getting recent assignments: {e}")
        raise HTTPException(status_code=400, detail=str(e))
