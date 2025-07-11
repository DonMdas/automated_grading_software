from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Annotation, Submission, User
from app.api.auth import get_current_user_dependency as get_current_user
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter()

class AnnotationCreate(BaseModel):
    submission_id: int
    x_coordinate: float
    y_coordinate: float
    width: float
    height: float
    annotation_text: str
    annotation_type: str  # highlight, comment, correction

class AnnotationResponse(BaseModel):
    id: int
    x_coordinate: float
    y_coordinate: float
    width: float
    height: float
    annotation_text: str
    annotation_type: str
    annotator_name: str
    created_at: str

@router.post("/annotations")
async def create_annotation(
    annotation_data: AnnotationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new annotation on a submission"""
    
    # Verify submission exists
    submission = db.query(Submission).filter(Submission.id == annotation_data.submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Verify access
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        if current_user.role != "developer":
            raise HTTPException(status_code=403, detail="Access denied")
    
    annotation = Annotation(
        submission_id=annotation_data.submission_id,
        annotator_id=current_user.id,
        x_coordinate=annotation_data.x_coordinate,
        y_coordinate=annotation_data.y_coordinate,
        width=annotation_data.width,
        height=annotation_data.height,
        annotation_text=annotation_data.annotation_text,
        annotation_type=annotation_data.annotation_type
    )
    
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    
    return {
        "id": annotation.id,
        "submission_id": annotation.submission_id,
        "x_coordinate": annotation.x_coordinate,
        "y_coordinate": annotation.y_coordinate,
        "width": annotation.width,
        "height": annotation.height,
        "annotation_text": annotation.annotation_text,
        "annotation_type": annotation.annotation_type,
        "created_at": annotation.created_at.isoformat()
    }

@router.get("/submissions/{submission_id}/annotations")
async def get_submission_annotations(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[AnnotationResponse]:
    """Get all annotations for a submission"""
    
    # Verify submission exists and access
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if current_user.role == "teacher" and submission.assignment.teacher_id != current_user.id:
        if current_user.role != "developer":
            raise HTTPException(status_code=403, detail="Access denied")
    
    annotations = db.query(Annotation).filter(Annotation.submission_id == submission_id).all()
    
    return [
        {
            "id": a.id,
            "x_coordinate": a.x_coordinate,
            "y_coordinate": a.y_coordinate,
            "width": a.width,
            "height": a.height,
            "annotation_text": a.annotation_text,
            "annotation_type": a.annotation_type,
            "annotator_name": a.annotator.full_name,
            "created_at": a.created_at.isoformat()
        }
        for a in annotations
    ]

@router.put("/annotations/{annotation_id}")
async def update_annotation(
    annotation_id: int,
    annotation_text: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update an annotation"""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    # Only the annotator or developer can update
    if annotation.annotator_id != current_user.id and current_user.role != "developer":
        raise HTTPException(status_code=403, detail="Access denied")
    
    annotation.annotation_text = annotation_text
    db.commit()
    
    return {
        "id": annotation.id,
        "annotation_text": annotation.annotation_text,
        "updated_at": annotation.created_at.isoformat()
    }

@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Delete an annotation"""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    # Only the annotator or developer can delete
    if annotation.annotator_id != current_user.id and current_user.role != "developer":
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(annotation)
    db.commit()
    
    return {"message": "Annotation deleted successfully"}

@router.get("/annotation-types")
async def get_annotation_types() -> Dict[str, List[Dict[str, str]]]:
    """Get available annotation types"""
    
    return {
        "types": [
            {"value": "highlight", "label": "Highlight", "color": "#ffeb3b"},
            {"value": "comment", "label": "Comment", "color": "#2196f3"},
            {"value": "correction", "label": "Correction", "color": "#f44336"},
            {"value": "praise", "label": "Praise", "color": "#4caf50"}
        ]
    }
