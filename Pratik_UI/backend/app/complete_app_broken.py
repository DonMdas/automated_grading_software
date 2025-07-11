"""
Complete AI Grading Application - Main FastAPI App

This is the complete integration that brings together:
- User authentication (username/password + Google OAuth)
- Google Classroom integration
- Database storage (PostgreSQL + MongoDB)
- OCR processing
- AI grading
- Results review and analytics
- Grade submission back to Google Classroom
"""

import logging
                'openid',
                'email',
                'profile',
                'https://www.googleapis.com/auth/classroom.courses.readonly',
                'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
                'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly'
            ]
        )
        
        # Set redirect URI
        flow.redirect_uri = 'http://localhost:8000/api/auth/google/callback'
        
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

@app.get("/api/auth/google/callback", summary="Google OAuth Callback")
async def google_oauth_callback(code: str, state: str):
    """Handle Google OAuth callback"""
    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        
        # Recreate flow
        flow = Flow.from_client_secrets_file(
            'client_secrets.json',
            scopes=[
                'openid',
                'email', 
                'profile',
                'https://www.googleapis.com/auth/classroom.courses.readonly',
                'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
                'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly'
            ],
            state=state
        )
        flow.redirect_uri = 'http://localhost:8000/api/auth/google/callback'
        
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
            url=f"http://localhost:3001/auth/google-success.html?token={access_token}&email={user.email}&name={user.full_name}"
        )
        
    except Exception as e:
        logger.error(f"❌ Google OAuth callback error: {e}")
        return RedirectResponse(
            url=f"http://localhost:3001/auth/google-error.html?error={str(e)}"
        )room integration
- Database storage (PostgreSQL + MongoDB)
- OCR processing
- AI grading
- Results review and analytics
- Grade submission back to Google Classroom
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import database connector
from app.db.connector import (
    initialize_database_connections,
    close_database_connections,
    get_postgres_session,
    get_mongo_collection
)

# Import services
from app.services.enhanced_google_classroom_service import classroom_service
from app.services.auth_service import auth_service
from app.services.enhanced_grading_service import enhanced_grading_service

# Import models
from app.models.models import User

# Import API modules
from app.api import auth, classroom, evaluation, analytics

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

# Pydantic models
class UserLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str

class SubmissionWorkflow(BaseModel):
    course_id: str
    assignment_id: str
    answer_key_file: str

class GradeReview(BaseModel):
    submission_id: str
    updated_score: float
    teacher_feedback: str
    approved: bool = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown
    """
    # Startup
    logger.info("🚀 Starting AI Grading Platform...")
    
    # Initialize database connections
    success = initialize_database_connections()
    if not success:
        logger.error("❌ Failed to initialize database connections")
        raise RuntimeError("Database initialization failed")
    
    logger.info("✅ Database connections initialized successfully!")
    
    # Initialize classroom service
    classroom_service_success = classroom_service.initialize() if hasattr(classroom_service, 'initialize') else True
    logger.info(f"📚 Google Classroom service: {'✅ Ready' if classroom_service_success else '⚠️ Limited functionality'}")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Shutting down AI Grading Platform...")
    close_database_connections()
    logger.info("✅ Database connections closed")

# Create FastAPI app
app = FastAPI(
    title="AI Automated Grading Platform",
    description="Complete grading solution with Google Classroom integration, OCR processing, and AI evaluation",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract current user from JWT token
    """
    try:
        # Extract token from Authorization header
        token = credentials.credentials
        
        # Decode JWT token using auth service
        user = auth_service.get_current_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "google_authenticated": user.google_access_token is not None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# --- Authentication Endpoints ---

@app.post("/api/auth/signup", summary="User Registration")
async def signup(user_data: UserSignup):
    """Register a new teacher account"""
    try:
        # Hash password and store user
        with get_postgres_session() as session:
            # This would use your actual user creation logic
            logger.info(f"📝 Creating user account for {user_data.email}")
            
        return {
            "message": "Account created successfully",
            "email": user_data.email
        }
    except Exception as e:
        logger.error(f"❌ Signup error: {e}")
        raise HTTPException(status_code=400, detail="Failed to create account")

@app.post("/api/auth/login", summary="User Login")
async def login(user_data: UserLogin):
    """Authenticate user with email/password"""
    try:
        # Verify credentials and generate JWT
        # This would use your actual authentication logic
        logger.info(f"🔐 Login attempt for {user_data.email}")
        
        # Mock response
        return {
            "access_token": "mock_jwt_token",
            "token_type": "bearer",
            "user": {
                "email": user_data.email,
                "role": "teacher"
            }
        }
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/auth/google", summary="Google OAuth Redirect")
async def google_oauth():
    """Initiate Google OAuth flow"""
    try:
        # This would use your existing Google OAuth logic
        logger.info("🔗 Initiating Google OAuth flow")
        return RedirectResponse("https://accounts.google.com/oauth2/mock_redirect")
    except Exception as e:
        logger.error(f"❌ Google OAuth error: {e}")
        raise HTTPException(status_code=500, detail="OAuth initialization failed")

# --- Google Classroom Integration Endpoints ---

@app.get("/api/classroom/courses", summary="Get User's Courses")
async def get_courses(current_user: Dict = Depends(get_current_user)):
    """Get user's Google Classroom courses"""
    try:
        courses = classroom_service.get_user_courses(current_user["user_id"])
        
        return {
            "courses": courses,
            "total": len(courses)
        }
    except Exception as e:
        logger.error(f"❌ Error getting courses: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve courses")

@app.get("/api/classroom/courses/{course_id}/assignments", summary="Get Course Assignments")
async def get_assignments(course_id: str, current_user: Dict = Depends(get_current_user)):
    """Get assignments for a specific course"""
    try:
        assignments = classroom_service.get_course_assignments(current_user["user_id"], course_id)
        
        return {
            "course_id": course_id,
            "assignments": assignments,
            "total": len(assignments)
        }
    except Exception as e:
        logger.error(f"❌ Error getting assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve assignments")

@app.get("/api/classroom/courses/{course_id}/assignments/{assignment_id}/submissions", 
         summary="Get Assignment Submissions")
async def get_submissions(course_id: str, assignment_id: str, current_user: Dict = Depends(get_current_user)):
    """Get student submissions for an assignment"""
    try:
        submissions = classroom_service.get_assignment_submissions(
            current_user["user_id"], course_id, assignment_id
        )
        
        return {
            "course_id": course_id,
            "assignment_id": assignment_id,
            "submissions": submissions,
            "total": len(submissions)
        }
    except Exception as e:
        logger.error(f"❌ Error getting submissions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve submissions")

# --- Complete Workflow Endpoints ---

@app.post("/api/workflow/process-assignment", summary="Complete Assignment Processing Workflow")
async def process_assignment_workflow(
    course_id: str = Form(...),
    assignment_id: str = Form(...),
    answer_key: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Dict = Depends(get_current_user)
):
    """
    Complete workflow: Download submissions, OCR, store in DB, grade, and prepare results
    """
    try:
        logger.info(f"🔄 Starting complete workflow for assignment {assignment_id}")
        
        # Save answer key file
        answer_key_path = f"/tmp/answer_key_{assignment_id}.pdf"
        with open(answer_key_path, "wb") as buffer:
            content = await answer_key.read()
            buffer.write(content)
        
        # Start the complete workflow
        result = classroom_service.process_submissions_workflow(
            current_user["user_id"],
            course_id,
            assignment_id,
            answer_key_path,
            background_tasks
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Workflow error: {e}")
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")

@app.get("/api/workflow/status/{task_id}", summary="Get Workflow Status")
async def get_workflow_status(task_id: str):
    """Get the status of a processing workflow"""
    try:
        status = classroom_service.get_workflow_status(task_id)
        return status
    except Exception as e:
        logger.error(f"❌ Error getting workflow status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflow status")

# --- Grading and Review Endpoints ---

@app.get("/api/grading/exams/{exam_id}/results", summary="Get Grading Results")
async def get_grading_results(exam_id: int, current_user: Dict = Depends(get_current_user)):
    """Get detailed grading results for an exam"""
    try:
        results = enhanced_grading_service.get_grading_results(exam_id)
        
        return results
    except Exception as e:
        logger.error(f"❌ Error getting grading results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve grading results")

@app.post("/api/grading/review", summary="Review and Update Grades")
async def review_grades(review_data: GradeReview, current_user: Dict = Depends(get_current_user)):
    """Allow teacher to review and update AI-generated grades"""
    try:
        # Update grades in database
        collection = get_mongo_collection("grading_results")
        
        # Get existing result
        existing = collection.find_one({"submission_id": review_data.submission_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Update with teacher review
        update_data = {
            "$set": {
                "teacher_review": {
                    "updated_score": review_data.updated_score,
                    "teacher_feedback": review_data.teacher_feedback,
                    "approved": review_data.approved,
                    "reviewed_at": datetime.utcnow(),
                    "reviewed_by": current_user["user_id"]
                },
                "final_score": review_data.updated_score,
                "status": "reviewed"
            }
        }
        
        collection.update_one(
            {"submission_id": review_data.submission_id},
            update_data
        )
        
        logger.info(f"✅ Grade reviewed for submission {review_data.submission_id}")
        
        return {
            "message": "Grade review saved successfully",
            "submission_id": review_data.submission_id,
            "final_score": review_data.updated_score
        }
        
    except Exception as e:
        logger.error(f"❌ Error reviewing grades: {e}")
        raise HTTPException(status_code=500, detail="Failed to save grade review")

@app.post("/api/grading/finalize/{exam_id}", summary="Finalize Grades")
async def finalize_grades(exam_id: int, current_user: Dict = Depends(get_current_user)):
    """Finalize grades and optionally submit back to Google Classroom"""
    try:
        # Get all reviewed grades
        collection = get_mongo_collection("grading_results")
        results = list(collection.find({"exam_id": exam_id}))
        
        finalized_count = 0
        for result in results:
            if result.get("teacher_review", {}).get("approved", False):
                # Mark as finalized
                collection.update_one(
                    {"_id": result["_id"]},
                    {"$set": {"status": "finalized", "finalized_at": datetime.utcnow()}}
                )
                finalized_count += 1
        
        logger.info(f"✅ Finalized {finalized_count} grades for exam {exam_id}")
        
        return {
            "message": f"Finalized {finalized_count} grades",
            "exam_id": exam_id,
            "finalized_count": finalized_count,
            "total_results": len(results)
        }
        
    except Exception as e:
        logger.error(f"❌ Error finalizing grades: {e}")
        raise HTTPException(status_code=500, detail="Failed to finalize grades")

# --- Analytics Endpoints ---

@app.get("/api/analytics/exams/{exam_id}", summary="Get Exam Analytics")
async def get_exam_analytics(exam_id: int, current_user: Dict = Depends(get_current_user)):
    """Get detailed analytics for an exam"""
    try:
        # Get results from database
        collection = get_mongo_collection("grading_results")
        results = list(collection.find({"exam_id": exam_id}))
        
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this exam")
        
        # Calculate analytics
        analytics = {
            "exam_id": exam_id,
            "total_submissions": len(results),
            "graded_submissions": len([r for r in results if r.get("status") != "pending"]),
            "reviewed_submissions": len([r for r in results if r.get("status") == "reviewed"]),
            "finalized_submissions": len([r for r in results if r.get("status") == "finalized"]),
            "average_score": 0,
            "score_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "question_analytics": {},
            "needs_review_count": len([r for r in results if r.get("needs_review", False)]),
            "completion_rate": 0
        }
        
        # Calculate score statistics
        scores = []
        for result in results:
            final_score = result.get("final_score")
            if final_score is None:
                summary = result.get("grading_results", {}).get("summary", {})
                final_score = summary.get("percentage", 0)
            
            if final_score:
                scores.append(final_score)
        
        if scores:
            analytics["average_score"] = sum(scores) / len(scores)
            analytics["completion_rate"] = (len(scores) / len(results)) * 100
            
            # Score distribution
            for score in scores:
                if score >= 90:
                    analytics["score_distribution"]["A"] += 1
                elif score >= 80:
                    analytics["score_distribution"]["B"] += 1
                elif score >= 70:
                    analytics["score_distribution"]["C"] += 1
                elif score >= 60:
                    analytics["score_distribution"]["D"] += 1
                else:
                    analytics["score_distribution"]["F"] += 1
        
        return analytics
        
    except Exception as e:
        logger.error(f"❌ Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate analytics")

@app.get("/api/analytics/teacher/{teacher_id}", summary="Get Teacher Analytics")
async def get_teacher_analytics(teacher_id: str, current_user: Dict = Depends(get_current_user)):
    """Get overall analytics for a teacher across all exams"""
    try:
        # This would aggregate across all teacher's exams
        # For now, return mock data
        analytics = {
            "teacher_id": teacher_id,
            "total_exams": 5,
            "total_submissions": 125,
            "average_grading_time": "4.5 minutes",
            "student_performance_trend": "improving",
            "most_challenging_topics": ["Calculus", "Statistics"],
            "automation_savings": "15 hours per week"
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"❌ Error getting teacher analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate teacher analytics")

# --- Health Check Endpoints ---

@app.get("/", summary="API Health Check")
def root():
    """Root endpoint - API health check"""
    return {
        "message": "AI Grading Platform API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health", summary="Detailed Health Check")
def health_check():
    """Detailed health check including database status"""
    from app.db.connector import db_connector
    
    # Test database connections using the global connector
    test_results = db_connector.test_connections()
    
    postgres_status = "connected" if test_results.get("postgres", False) else "disconnected"
    mongodb_status = "connected" if test_results.get("mongodb", False) else "disconnected"
    
    return {
        "api_status": "healthy",
        "database_status": {
            "postgresql": postgres_status,
            "mongodb": mongodb_status
        },
        "services": {
            "google_classroom": "available" if hasattr(classroom_service, 'get_user_courses') else "limited",
            "grading_engine": "available",
            "ocr_processing": "available"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# --- Service Status Endpoints ---

@app.get("/api/auth/status", summary="Authentication Service Status")
def auth_status():
    """Get authentication service status"""
    return {
        "service": "authentication",
        "status": "active",
        "features": ["username/password", "google_oauth"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/classroom/status", summary="Google Classroom Service Status")
def classroom_status():
    """Get Google Classroom service status"""
    return {
        "service": "google_classroom",
        "status": "active",
        "features": ["course_access", "assignment_retrieval", "submission_download"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/grading/status", summary="Grading Service Status")
def grading_status():
    """Get grading service status"""
    return {
        "service": "ai_grading",
        "status": "active",
        "features": ["auto_grading", "batch_processing", "custom_rubrics"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/analytics/status", summary="Analytics Service Status")
def analytics_status():
    """Get analytics service status"""
    return {
        "service": "analytics",
        "status": "active",
        "features": ["performance_metrics", "teacher_insights", "exam_analysis"],
        "timestamp": datetime.utcnow().isoformat()
    }

# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Global HTTP exception handler"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "timestamp": datetime.utcnow().isoformat()}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled Exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "timestamp": datetime.utcnow().isoformat()}
    )

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🌟 Starting Complete AI Grading Platform...")
    uvicorn.run(
        "complete_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
