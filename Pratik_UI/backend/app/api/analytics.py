from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.models.models import Assignment, Submission, User
from app.api.auth import get_current_user_dependency as get_current_user
from typing import List, Dict, Any
import json

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get analytics data for dashboard"""
    
    if current_user.role == "developer":
        # Developer analytics
        total_users = db.query(User).count()
        total_assignments = db.query(Assignment).count()
        total_submissions = db.query(Submission).count()
        
        # Grading accuracy metrics
        graded_submissions = db.query(Submission).filter(
            Submission.auto_score.isnot(None),
            Submission.human_score.isnot(None)
        ).all()
        
        accuracy_data = []
        if graded_submissions:
            for submission in graded_submissions:
                accuracy = 100 - abs(submission.auto_score - submission.human_score)
                accuracy_data.append(accuracy)
        
        avg_accuracy = sum(accuracy_data) / len(accuracy_data) if accuracy_data else 0
        
        return {
            "total_users": total_users,
            "total_assignments": total_assignments,
            "total_submissions": total_submissions,
            "average_grading_accuracy": round(avg_accuracy, 2),
            "user_roles": db.query(User.role, func.count(User.id)).group_by(User.role).all(),
            "recent_submissions": [
                {
                    "id": s.id,
                    "student_name": s.student_name,
                    "assignment_title": s.assignment.title,
                    "status": s.status,
                    "auto_score": s.auto_score,
                    "created_at": s.created_at.isoformat()
                }
                for s in db.query(Submission).order_by(Submission.created_at.desc()).limit(10).all()
            ]
        }
    
    elif current_user.role == "teacher":
        # Teacher analytics
        teacher_assignments = db.query(Assignment).filter(Assignment.teacher_id == current_user.id).all()
        assignment_ids = [a.id for a in teacher_assignments]
        
        total_assignments = len(teacher_assignments)
        total_submissions = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids)
        ).count()
        
        pending_submissions = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status == "pending"
        ).count()
        
        graded_submissions = db.query(Submission).filter(
            Submission.assignment_id.in_(assignment_ids),
            Submission.status == "graded"
        ).count()
        
        return {
            "total_assignments": total_assignments,
            "total_submissions": total_submissions,
            "pending_submissions": pending_submissions,
            "graded_submissions": graded_submissions,
            "assignments": [
                {
                    "id": a.id,
                    "title": a.title,
                    "submission_count": db.query(Submission).filter(Submission.assignment_id == a.id).count(),
                    "created_at": a.created_at.isoformat()
                }
                for a in teacher_assignments
            ]
        }

@router.get("/submissions/{assignment_id}")
async def get_submission_analytics(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get analytics for a specific assignment's submissions"""
    
    # Verify access to assignment
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if current_user.role == "teacher" and assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
    
    # Score distribution
    scores = [s.auto_score for s in submissions if s.auto_score is not None]
    score_ranges = {
        "0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0
    }
    
    for score in scores:
        if score <= 20:
            score_ranges["0-20"] += 1
        elif score <= 40:
            score_ranges["21-40"] += 1
        elif score <= 60:
            score_ranges["41-60"] += 1
        elif score <= 80:
            score_ranges["61-80"] += 1
        else:
            score_ranges["81-100"] += 1
    
    return {
        "assignment_title": assignment.title,
        "total_submissions": len(submissions),
        "average_score": sum(scores) / len(scores) if scores else 0,
        "score_distribution": score_ranges,
        "status_counts": {
            "pending": len([s for s in submissions if s.status == "pending"]),
            "graded": len([s for s in submissions if s.status == "graded"]),
            "reviewed": len([s for s in submissions if s.status == "reviewed"])
        },
        "submissions": [
            {
                "id": s.id,
                "student_name": s.student_name,
                "auto_score": s.auto_score,
                "human_score": s.human_score,
                "status": s.status,
                "created_at": s.created_at.isoformat()
            }
            for s in submissions
        ]
    }
