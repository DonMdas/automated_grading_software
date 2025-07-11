from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Assignment, Submission, User
from app.api.auth import get_current_user_dependency as get_current_user
from app.services.ocr_service import OCRService
from app.services.grading_service import GradingService
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

router = APIRouter()

class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    max_score: float = 100.0
    classroom_id: Optional[str] = None

class SubmissionResponse(BaseModel):
    id: int
    student_name: str
    student_email: str
    auto_score: Optional[float]
    human_score: Optional[float]
    status: str
    created_at: str

@router.post("/assignments")
async def create_assignment(
    assignment_data: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new assignment"""
    
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    
    assignment = Assignment(
        title=assignment_data.title,
        description=assignment_data.description,
        teacher_id=current_user.id,
        max_score=assignment_data.max_score,
        classroom_id=assignment_data.classroom_id
    )
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "max_score": assignment.max_score,
        "created_at": assignment.created_at.isoformat()
    }

@router.get("/assignments")
async def get_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get user's assignments"""
    
    if current_user.role == "teacher":
        assignments = db.query(Assignment).filter(Assignment.teacher_id == current_user.id).all()
    else:
        assignments = db.query(Assignment).all()
    
    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "max_score": a.max_score,
            "teacher_name": a.teacher.full_name if a.teacher else "Unknown",
            "submission_count": len(a.submissions),
            "created_at": a.created_at.isoformat()
        }
        for a in assignments
    ]

@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    file: UploadFile = File(...),
    student_name: str = Form(...),
    student_email: str = Form(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Submit an assignment for grading"""
    
    # Verify assignment exists
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Save uploaded file
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{assignment_id}_{student_email}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    # Perform OCR
    ocr_service = OCRService()
    try:
        ocr_text = ocr_service.extract_text(file_path)
    except Exception as e:
        ocr_text = f"OCR failed: {str(e)}"
    
    # Create submission
    submission = Submission(
        assignment_id=assignment_id,
        student_email=student_email,
        student_name=student_name,
        file_path=file_path,
        original_filename=file.filename,
        ocr_text=ocr_text,
        status="pending"
    )
    
    db.add(submission)
    db.commit()
    db.refresh(submission)
    
    # Perform auto-grading
    grading_service = GradingService(db)
    try:
        auto_score = grading_service.auto_grade_submission(submission.id)
        submission.auto_score = auto_score
        submission.status = "graded"
        db.commit()
    except Exception as e:
        print(f"Auto-grading failed: {e}")
    
    return {
        "id": submission.id,
        "message": "Submission uploaded and processed successfully",
        "auto_score": submission.auto_score,
        "status": submission.status
    }

@router.get("/assignments/{assignment_id}/submissions")
async def get_assignment_submissions(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[SubmissionResponse]:
    """Get all submissions for an assignment"""
    
    # Verify access
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if current_user.role == "teacher" and assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    submissions = db.query(Submission).filter(Submission.assignment_id == assignment_id).all()
    
    return [
        {
            "id": s.id,
            "student_name": s.student_name,
            "student_email": s.student_email,
            "auto_score": s.auto_score,
            "human_score": s.human_score,
            "status": s.status,
            "original_filename": s.original_filename,
            "created_at": s.created_at.isoformat()
        }
        for s in submissions
    ]

@router.put("/submissions/{submission_id}/grade")
async def update_submission_grade(
    submission_id: int,
    human_score: float = Form(...),
    feedback: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update manual grade for a submission"""
    
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Verify access
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    submission.human_score = human_score
    submission.feedback = feedback
    submission.status = "reviewed"
    
    db.commit()
    
    return {
        "id": submission.id,
        "human_score": submission.human_score,
        "feedback": submission.feedback,
        "status": submission.status
    }
