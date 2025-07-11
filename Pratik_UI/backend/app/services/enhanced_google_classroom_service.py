"""
Enhanced Google Classroom Service with Database Integration

This service handles the complete workflow:
1. Google Classroom authentication and course access
2. Submission download and OCR processing
3. Database storage using the unified connector
4. Integration with the grading FastAPI
"""

import os
import json
import uuid
import logging
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fastapi import HTTPException, BackgroundTasks
import requests
import aiofiles

# Import database connector
from app.db.connector import get_postgres_session, get_mongo_collection
from sqlalchemy import text

# Import OCR processors
from .studentanswer import extract_student_answers_to_json
from .extract_answer_key import extract_answer_key_to_json

# Google imports
try:
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("WARNING: Google libraries not available")

logger = logging.getLogger(__name__)

class EnhancedGoogleClassroomService:
    """
    Enhanced Google Classroom service with complete workflow integration
    """
    
    def __init__(self):
        self.credentials_cache = {}
        self.grading_api_url = "http://localhost:8001"  # Enhanced grading API
        
    def authenticate_user(self, user_id: str, credentials_dict: Dict[str, Any]) -> bool:
        """
        Store user's Google credentials for future use
        
        Args:
            user_id: User identifier
            credentials_dict: Google OAuth credentials
            
        Returns:
            bool: Success status
        """
        try:
            if GOOGLE_AVAILABLE:
                # Convert dict to Credentials object
                credentials = Credentials.from_authorized_user_info(credentials_dict)
                self.credentials_cache[user_id] = credentials
                
                # Store in database
                collection = get_mongo_collection("user_credentials")
                document = {
                    "user_id": user_id,
                    "credentials": credentials_dict,
                    "created_at": datetime.utcnow(),
                    "provider": "google_classroom"
                }
                collection.replace_one({"user_id": user_id}, document, upsert=True)
                
                logger.info(f"✅ Stored Google credentials for user {user_id}")
                return True
            else:
                logger.warning("Google libraries not available - using mock authentication")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error storing credentials: {e}")
            return False
    
    def get_user_credentials(self, user_id: str) -> Optional[Credentials]:
        """
        Get user's Google credentials
        
        Args:
            user_id: User identifier
            
        Returns:
            Credentials object or None
        """
        try:
            # Check cache first
            if user_id in self.credentials_cache:
                return self.credentials_cache[user_id]
            
            # Get from database
            collection = get_mongo_collection("user_credentials")
            document = collection.find_one({"user_id": user_id})
            
            if document and GOOGLE_AVAILABLE:
                credentials = Credentials.from_authorized_user_info(document["credentials"])
                self.credentials_cache[user_id] = credentials
                return credentials
                
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting credentials: {e}")
            return None
    
    def get_user_courses(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's Google Classroom courses
        
        Args:
            user_id: User identifier
            
        Returns:
            List of course information
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if not credentials or not GOOGLE_AVAILABLE:
                # Return mock data for testing
                return [
                    {
                        "id": "course_001",
                        "name": "Mathematics 101",
                        "section": "A",
                        "description": "Basic Mathematics Course",
                        "teacher": "John Doe"
                    },
                    {
                        "id": "course_002", 
                        "name": "Physics 201",
                        "section": "B",
                        "description": "Advanced Physics Course",
                        "teacher": "Jane Smith"
                    }
                ]
            
            service = build('classroom', 'v1', credentials=credentials)
            courses_result = service.courses().list().execute()
            courses = courses_result.get('courses', [])
            
            # Store courses in database
            collection = get_mongo_collection("user_courses")
            document = {
                "user_id": user_id,
                "courses": courses,
                "updated_at": datetime.utcnow()
            }
            collection.replace_one({"user_id": user_id}, document, upsert=True)
            
            logger.info(f"✅ Retrieved {len(courses)} courses for user {user_id}")
            return courses
            
        except Exception as e:
            logger.error(f"❌ Error getting courses: {e}")
            return []
    
    def get_course_assignments(self, user_id: str, course_id: str) -> List[Dict[str, Any]]:
        """
        Get assignments for a specific course
        
        Args:
            user_id: User identifier
            course_id: Google Classroom course ID
            
        Returns:
            List of assignment information
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if not credentials or not GOOGLE_AVAILABLE:
                # Return mock data
                return [
                    {
                        "id": "assignment_001",
                        "title": "Midterm Exam",
                        "description": "Mathematics midterm examination",
                        "dueDate": "2025-07-15",
                        "maxPoints": 100,
                        "state": "PUBLISHED"
                    },
                    {
                        "id": "assignment_002",
                        "title": "Final Project",
                        "description": "Final mathematics project",
                        "dueDate": "2025-07-30",
                        "maxPoints": 150,
                        "state": "PUBLISHED"
                    }
                ]
            
            service = build('classroom', 'v1', credentials=credentials)
            assignments = service.courses().courseWork().list(courseId=course_id).execute()
            
            course_work = assignments.get('courseWork', [])
            
            # Store assignments in database
            collection = get_mongo_collection("course_assignments")
            document = {
                "user_id": user_id,
                "course_id": course_id,
                "assignments": course_work,
                "updated_at": datetime.utcnow()
            }
            collection.replace_one(
                {"user_id": user_id, "course_id": course_id}, 
                document, 
                upsert=True
            )
            
            logger.info(f"✅ Retrieved {len(course_work)} assignments for course {course_id}")
            return course_work
            
        except Exception as e:
            logger.error(f"❌ Error getting assignments: {e}")
            return []
    
    def get_assignment_submissions(self, user_id: str, course_id: str, assignment_id: str) -> List[Dict[str, Any]]:
        """
        Get student submissions for an assignment
        
        Args:
            user_id: User identifier
            course_id: Google Classroom course ID
            assignment_id: Assignment ID
            
        Returns:
            List of submission information
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if not credentials or not GOOGLE_AVAILABLE:
                # Return mock submissions
                return [
                    {
                        "id": "submission_001",
                        "userId": "student_001",
                        "assignmentSubmission": {
                            "attachments": [
                                {
                                    "driveFile": {
                                        "id": "file_001",
                                        "title": "student_001_answers.pdf",
                                        "alternateLink": "https://drive.google.com/file/d/mock_file_001"
                                    }
                                }
                            ]
                        },
                        "state": "TURNED_IN",
                        "creationTime": "2025-07-04T10:00:00Z"
                    },
                    {
                        "id": "submission_002",
                        "userId": "student_002", 
                        "assignmentSubmission": {
                            "attachments": [
                                {
                                    "driveFile": {
                                        "id": "file_002",
                                        "title": "student_002_answers.pdf",
                                        "alternateLink": "https://drive.google.com/file/d/mock_file_002"
                                    }
                                }
                            ]
                        },
                        "state": "TURNED_IN",
                        "creationTime": "2025-07-04T10:30:00Z"
                    }
                ]
            
            service = build('classroom', 'v1', credentials=credentials)
            submissions = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id,
                courseWorkId=assignment_id
            ).execute()
            
            student_submissions = submissions.get('studentSubmissions', [])
            
            # Store submissions metadata in database
            collection = get_mongo_collection("assignment_submissions")
            document = {
                "user_id": user_id,
                "course_id": course_id,
                "assignment_id": assignment_id,
                "submissions": student_submissions,
                "updated_at": datetime.utcnow()
            }
            collection.replace_one(
                {"user_id": user_id, "course_id": course_id, "assignment_id": assignment_id},
                document,
                upsert=True
            )
            
            logger.info(f"✅ Retrieved {len(student_submissions)} submissions for assignment {assignment_id}")
            return student_submissions
            
        except Exception as e:
            logger.error(f"❌ Error getting submissions: {e}")
            return []

# Global instance
classroom_service = EnhancedGoogleClassroomService()
