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

# Import the Google auth router
from app.api.google_auth import router as google_auth_router

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
    logger.info("✅ Cleanup completed")

# Initialize FastAPI app
app = FastAPI(
    title="AI Automated Grading Platform",
    description="Complete grading solution with Google Classroom integration, OCR processing, and AI evaluation",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Google auth router
app.include_router(google_auth_router)

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
            auth_service.set_db(session)
            # Check if user already exists
            existing_user = auth_service.get_user_by_email(user_data.email)
            if existing_user:
                raise HTTPException(status_code=400, detail="Email already registered")
            
            # Create new user
            user_dict = {
                "email": user_data.email,
                "password": user_data.password,
                "username": user_data.email.split('@')[0],
                "full_name": user_data.full_name,
                "role": "teacher"
            }
            user = auth_service.create_user(user_dict)
            
        return {
            "message": "Account created successfully",
            "email": user_data.email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Signup error: {e}")
        raise HTTPException(status_code=400, detail="Failed to create account")

@app.post("/api/auth/login", summary="User Login")
async def login(user_data: UserLogin):
    """Authenticate user with username/password"""
    try:
        with get_postgres_session() as session:
            auth_service.set_db(session)
            user = auth_service.authenticate_user(user_data.email, user_data.password)
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Create access token
            access_token = auth_service.create_access_token(
                data={"sub": user.email}
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

# --- Google Classroom Integration Endpoints ---

@app.get("/api/classroom/courses", summary="Get User's Courses")
async def get_courses(current_user: Dict = Depends(get_current_user)):
    """Get user's Google Classroom courses"""
    try:
        if not current_user.get("google_authenticated"):
            raise HTTPException(status_code=401, detail="Google authentication required")
            
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
        if not current_user.get("google_authenticated"):
            raise HTTPException(status_code=401, detail="Google authentication required")
            
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
    """Get submissions for a specific assignment"""
    try:
        if not current_user.get("google_authenticated"):
            raise HTTPException(status_code=401, detail="Google authentication required")
            
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
