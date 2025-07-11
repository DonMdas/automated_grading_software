"""
FastAPI Application Startup with Unified Database Connector

This shows how to integrate the database connector with your FastAPI application
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from typing import Dict, Any
import logging

# Import the unified connector
from app.db.connector import (
    initialize_database_connections,
    close_database_connections,
    get_postgres_session,
    get_mongo_collection
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown
    """
    # Startup
    logger.info("🚀 Starting up AI Grading Application...")
    
    # Initialize database connections
    success = initialize_database_connections()
    if not success:
        logger.error("❌ Failed to initialize database connections")
        raise RuntimeError("Database initialization failed")
    
    logger.info("✅ Database connections initialized successfully!")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("🛑 Shutting down AI Grading Application...")
    close_database_connections()
    logger.info("✅ Database connections closed")

# Create FastAPI app with lifespan
app = FastAPI(
    title="AI Automated Grading Platform",
    description="A comprehensive grading system with Google Classroom integration",
    version="1.0.0",
    lifespan=lifespan
)

# Example API endpoints using the connector

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AI Automated Grading Platform API", "status": "running"}

@app.get("/health/databases")
async def check_databases():
    """Health check for database connections"""
    try:
        from app.db.connector import db_connector
        
        # Test connections
        test_results = db_connector.test_connections()
        
        return {
            "status": "success" if all(test_results.values()) else "partial",
            "databases": test_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")

@app.post("/api/submissions/{submission_id}/process")
async def process_submission(submission_id: str, submission_data: Dict[str, Any]):
    """
    Example endpoint: Process a student submission
    This would be called after OCR processing
    """
    try:
        # Store in MongoDB
        collection = get_mongo_collection("student_submissions")
        document = {
            "submission_id": submission_id,
            "processed_data": submission_data,
            "status": "processed"
        }
        result = collection.insert_one(document)
        
        return {
            "success": True,
            "submission_id": submission_id,
            "document_id": str(result.inserted_id)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/api/exams/{exam_id}/grade")
async def grade_submissions(exam_id: int):
    """
    Example endpoint: Trigger grading for an exam
    This would integrate with your grading_fastapi engine
    """
    try:
        # Get submissions to grade from MongoDB
        collection = get_mongo_collection("student_submissions")
        submissions = list(collection.find({"exam_id": exam_id, "status": "processed"}))
        
        # Here you would call your grading engine
        # from grading_fastapi import grade_submission
        # results = []
        # for submission in submissions:
        #     result = grade_submission(submission, answer_key)
        #     results.append(result)
        
        # For demo, return the count
        return {
            "success": True,
            "exam_id": exam_id,
            "submissions_found": len(submissions),
            "message": "Grading would be triggered here"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grading failed: {str(e)}")

@app.get("/api/analytics/{course_id}")
async def get_course_analytics(course_id: str):
    """
    Example endpoint: Get analytics for a course
    Combines data from PostgreSQL and MongoDB
    """
    try:
        # Get data from PostgreSQL
        with get_postgres_session() as session:
            # This would use your actual schema
            # For demo, return mock data
            pass
        
        # Get data from MongoDB
        collection = get_mongo_collection("grading_results")
        # Mock analytics data
        
        return {
            "course_id": course_id,
            "total_submissions": 45,
            "graded_submissions": 42,
            "average_score": 78.5,
            "analytics": "Combined from PostgreSQL and MongoDB"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🌟 Starting AI Grading Platform...")
    uvicorn.run(
        "main_with_connector:app",
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
