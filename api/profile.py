"""
Profile API endpoints for the AI Studio application.
"""

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db_service import db_service

router = APIRouter()

@router.get("/api/profile/recent-activity")
async def get_recent_activity(current_user = Depends(get_current_user)):
    """Get recent activity for the user"""
    try:
        # For now, return mock data. In a real implementation, 
        # this would query the database for user activity
        recent_activity = [
            {
                "type": "grading",
                "description": "Completed grading for Math Test",
                "time": "2 hours ago"
            },
            {
                "type": "submission",
                "description": "New submissions received for English Essay",
                "time": "1 day ago"
            },
            {
                "type": "login",
                "description": "Logged in to the platform",
                "time": "3 days ago"
            }
        ]
        return recent_activity
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent activity: {str(e)}")

@router.get("/api/profile/statistics")
async def get_profile_statistics(current_user = Depends(get_current_user)):
    """Get statistics for the user profile"""
    try:
        # Get total assignments/coursework
        total_assignments = db_service.count_assignments()
        
        # Get total submissions
        total_submissions = db_service.count_submissions()
        
        # Get total graded submissions
        total_graded = db_service.count_graded_submissions()
        
        # Calculate average grade from grading results
        avg_grade = db_service.calculate_average_grade()
        
        return {
            "totalAssignments": total_assignments,
            "totalSubmissions": total_submissions,
            "totalGraded": total_graded,
            "avgGrade": avg_grade
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile statistics: {str(e)}")
