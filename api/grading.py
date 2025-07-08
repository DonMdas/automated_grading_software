"""
Grading API endpoints for the AI Studio application.
"""

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
from background_tasks_v2 import process_grading_in_background
from db_service import db_service

router = APIRouter()

@router.post("/api/grading/start/{coursework_id}")
async def start_grading_process(
    coursework_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    grading_version: str = "v2"
):
    """
    Start the grading process for a coursework after OCR is complete.
    Only submissions with OCR_COMPLETE status will be processed.
    """
    # Check if there are any OCR-complete submissions
    ocr_complete_submissions = db_service.get_submissions_by_status(
        coursework_id, ["OCR_COMPLETE"]
    )
    
    if not ocr_complete_submissions:
        raise HTTPException(
            status_code=400, 
            detail="No OCR-complete submissions found. Please wait for OCR processing to complete first."
        )
    
    # Check if grading is already in progress
    existing_task = db_service.get_grading_task_by_assignment(
        coursework_id, status=["PENDING", "RUNNING"]
    )
    
    if existing_task:
        return {"message": "Grading is already in progress", "task_id": existing_task.task_id}
    
    # Create new grading task
    task_id = str(uuid.uuid4())
    grading_task = db_service.create_grading_task(
        task_id=task_id,
        assignment_id=coursework_id,
        grading_version=grading_version
    )
    
    # Start background task
    background_tasks.add_task(
        process_grading_in_background,
        task_id,
        coursework_id,
        grading_version
    )
    
    return {
        "message": "Grading process started in background",
        "task_id": task_id,
        "grading_version": grading_version,
        "submissions_to_grade": len(ocr_complete_submissions)
    }

@router.get("/api/grading/status/{task_id}")
async def get_grading_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get the status of a grading task."""
    grading_task = db_service.get_grading_task(task_id)
    if not grading_task:
        raise HTTPException(status_code=404, detail="Grading task not found")
    
    return {
        "task_id": grading_task.task_id,
        "coursework_id": grading_task.coursework_id,
        "grading_version": grading_task.grading_version,
        "status": grading_task.status,
        "progress": grading_task.progress,
        "message": grading_task.message,
        "result": json.loads(grading_task.result) if grading_task.result else None,
        "created_at": grading_task.created_at,
        "completed_at": grading_task.completed_at
    }

@router.get("/api/grading/tasks/{coursework_id}")
async def get_grading_tasks(
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all grading tasks for a specific coursework."""
    tasks = db_service.get_grading_tasks_by_assignment(coursework_id)
    
    return [{
        "task_id": task.task_id,
        "grading_version": task.grading_version,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "created_at": task.created_at,
        "completed_at": task.completed_at
    } for task in tasks]

@router.get("/api/grading/test-spans/{coursework_id}/{student_id}")
async def test_span_extraction(
    coursework_id: str,
    student_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Test endpoint to verify span extraction logic"""
    from database import MongoCollections
    
    try:
        # Get grading results from MongoDB
        collection = MongoCollections.get_collection("grading_results")
        grading_document = collection.find_one({
            "assignment_id": coursework_id,
            "student_id": student_id
        })
        
        if not grading_document:
            return {"error": "No grading results found", "coursework_id": coursework_id, "student_id": student_id}
        
        grading_results = grading_document.get("grading_results", [])
        if not grading_results:
            return {"error": "No grading results in document"}
        
        # Test span extraction on first question
        first_result = grading_results[0]
        spans = first_result.get("spans", [])
        meta = first_result.get("meta", {})
        original_answer = meta.get("original_answer", "")
        
        extracted_components = []
        
        if spans and original_answer:
            for span in spans:
                if isinstance(span, dict):
                    label = span.get("label", "Unknown")
                    
                    # Clean up label
                    if "(" in label and ")" in label:
                        label = label.split("(")[0].strip()
                    
                    # Extract text using start/end positions
                    if "start" in span and "end" in span:
                        try:
                            start = int(span["start"])
                            end = int(span["end"])
                            if start >= 0 and end <= len(original_answer) and start < end:
                                text = original_answer[start:end].strip()
                                if text:
                                    extracted_components.append({
                                        "label": label,
                                        "content": text,
                                        "original_span": span
                                    })
                        except (ValueError, TypeError):
                            pass
        
        return {
            "coursework_id": coursework_id,
            "student_id": student_id,
            "original_answer": original_answer,
            "spans": spans,
            "extracted_components": extracted_components,
            "component_count": len(extracted_components)
        }
        
    except Exception as e:
        return {"error": str(e)}
