"""
Evaluation API endpoints for the AI Studio application.
"""

import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from auth import get_current_user
from services.google_services import get_classroom_service
from background_tasks import process_and_download_submissions
from config import SERVER_DATA_DIR

router = APIRouter()

@router.post("/api/evaluate/coursework/{course_id}/{coursework_id}")
async def start_evaluation_process(
    course_id: str, 
    coursework_id: str, 
    background_tasks: BackgroundTasks,
    answer_key: UploadFile = File(...),
    grading_version: str = Form("v2"),  # Accept grading version from form data
    service=Depends(get_classroom_service), 
    db: Session = Depends(get_db)
):
    """
    Start the evaluation process for a coursework.
    Uploads answer key and processes submissions in the background.
    """
    print(f"Starting bulk evaluation for coursework {coursework_id} with grading version {grading_version}")
    
    # Validate grading version
    if grading_version not in ["v1", "v2"]:
        grading_version = "v2"  # Default to v2 if invalid
        print(f"Invalid grading version provided, defaulting to v2")
    
    assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
    assignment_dir.mkdir(parents=True, exist_ok=True)
    answer_key_path = assignment_dir / "answer_key.pdf"
    
    with open(answer_key_path, "wb") as buffer:
        shutil.copyfileobj(answer_key.file, buffer)
        
    print(f"Saved answer key to {answer_key_path}")
    
    # Pass the session maker to the background task
    background_tasks.add_task(
        process_and_download_submissions, 
        course_id, 
        coursework_id, 
        str(answer_key_path), # Pass path as a string
        service, 
        SessionLocal,  # Pass the session maker
        grading_version  # Pass grading version
    )
    
    return {
        "message": f"Answer key received. OCR and student submission downloads are running in the background using grading version {grading_version}."
    }
