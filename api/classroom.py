"""
Google Classroom API endpoints for the AI Studio application.
"""

from fastapi import APIRouter, Depends, HTTPException
from services.google_services import get_classroom_service

router = APIRouter()

@router.get("/api/classroom/courses")
async def get_courses(service=Depends(get_classroom_service)):
    """Get all active courses for the authenticated user."""
    try:
        results = service.courses().list(teacherId="me", courseStates=['ACTIVE']).execute()
        return results.get('courses', [])
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to fetch courses: {e}")

@router.get("/api/classroom/courses/{course_id}/coursework")
async def get_coursework(course_id: str, service=Depends(get_classroom_service)):
    """Get all coursework for a specific course."""
    try:
        results = service.courses().courseWork().list(courseId=course_id).execute()
        return results.get('courseWork', [])
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to fetch coursework: {e}")

@router.get("/api/classroom/courses/{course_id}/coursework/{coursework_id}/submissions")
async def get_submissions(course_id: str, coursework_id: str, service=Depends(get_classroom_service)):
    """Get all submissions for a specific coursework."""
    try:
        submission_results = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, 
            courseWorkId=coursework_id
        ).execute()
        submissions = submission_results.get('studentSubmissions', [])
        enriched_submissions = []
        
        for sub in submissions:
            student_name = "Unknown Student"
            try:
                student_profile = service.userProfiles().get(userId=sub.get('userId')).execute()
                student_name = student_profile.get('name', {}).get('fullName', student_name)
            except Exception: 
                pass
            enriched_submissions.append({
                "id": sub.get('id'), 
                "studentName": student_name, 
                "state": sub.get('state')
            })
        return enriched_submissions
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {e}")
