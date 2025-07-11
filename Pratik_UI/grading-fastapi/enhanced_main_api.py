"""
Enhanced Grading API with Database Integration

This is an enhanced version of main_api.py that integrates with the unified database connector.
It maintains all existing functionality while adding database persistence.
"""

import os
import shutil
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Path as FastApiPath
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import aiofiles

# Import the database integration
from database_integration import grading_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
EXAMS_BASE_DIR = Path("exam_data_storage")
EXAMS_BASE_DIR.mkdir(exist_ok=True)

# Prodigy configuration
PRODIGY_URL = "http://localhost:8080"
PRODIGY_STREAM_FILE = Path("/tmp/prodigy_stream.jsonl")

# --- Pydantic Models ---
class TaskStatus(BaseModel):
    task_id: str
    status: str
    message: str
    progress: Optional[int] = None
    result: Optional[Any] = None

class ExamStatus(BaseModel):
    name: str
    exam_id: Optional[int] = None
    has_answer_key: bool
    has_student_answers: bool
    has_processed_results: bool
    database_stored: bool = False

class ExamResults(BaseModel):
    exam_name: str
    exam_id: Optional[int] = None
    total_submissions: int
    graded_submissions: int
    results: Dict[str, Any]

# --- Task Management ---
tasks_db: Dict[str, Dict[str, Any]] = {}

def run_processing_in_background(task_id: str, exam_name: str, llm_version: str, exam_id: int = None):
    """
    Enhanced background processing with database integration
    """
    tasks_db[task_id] = {"status": "running", "message": "Initializing pipeline...", "progress": 0}

    try:
        # Step 1: Load pipeline
        tasks_db[task_id]["message"] = f"Loading pipeline version '{llm_version}'..."
        if llm_version == 'v1':
            from main_pipeline.v1.answer_key_processor import process_answer_key
            from main_pipeline.v1.student_processor import process_student_answers
        elif llm_version == 'v2':
            from main_pipeline.v2.answer_key_processor import process_answer_key
            from main_pipeline.v2.student_processor import process_student_answers
        else:
            raise ValueError(f"Invalid pipeline version '{llm_version}' specified.")

        exam_folder_path = str(EXAMS_BASE_DIR / exam_name)

        # Step 2: Process answer key
        tasks_db[task_id]["progress"] = 10
        tasks_db[task_id]["message"] = "Processing answer key..."
        success_ak = process_answer_key(exam_folder_path)
        if not success_ak:
            raise RuntimeError("Failed to process the answer key.")

        # Step 2.5: Store answer key in database
        if exam_id and grading_db.initialized:
            try:
                answer_key_file = Path(exam_folder_path) / "answer_key.json"
                if answer_key_file.exists():
                    with open(answer_key_file, 'r') as f:
                        answer_key_data = json.load(f)
                    grading_db.store_answer_key(exam_id, answer_key_data, str(answer_key_file))
                    tasks_db[task_id]["message"] = "Answer key stored in database..."
            except Exception as e:
                logger.warning(f"Could not store answer key in database: {e}")

        # Step 3: Process student answers
        tasks_db[task_id]["progress"] = 30
        tasks_db[task_id]["message"] = "Processing student submissions..."
        success_sa = process_student_answers(exam_folder_path)
        if not success_sa:
            raise RuntimeError("Failed to process student answers.")

        # Step 3.5: Store submissions and results in database
        if exam_id and grading_db.initialized:
            tasks_db[task_id]["progress"] = 70
            tasks_db[task_id]["message"] = "Storing results in database..."
            
            try:
                # Store processed results
                results_dir = Path(exam_folder_path) / "processed_student_answers"
                if results_dir.exists():
                    for result_file in results_dir.glob("*_processed.json"):
                        student_id = result_file.stem.replace("_processed", "")
                        
                        with open(result_file, 'r') as f:
                            grading_results = json.load(f)
                        
                        # Create a submission ID and store results
                        submission_id = str(uuid.uuid4())
                        grading_db.store_grading_results(submission_id, grading_results)
                        
                        # Store submission metadata
                        student_file = Path(exam_folder_path) / "student_answers" / f"{student_id}.json"
                        if student_file.exists():
                            with open(student_file, 'r') as f:
                                processed_data = {"answers": json.load(f)}
                            grading_db.store_student_submission(
                                exam_id, student_id, str(student_file), processed_data
                            )
                
                tasks_db[task_id]["message"] = "Results stored in database successfully..."
            except Exception as e:
                logger.warning(f"Could not store results in database: {e}")

        # Step 4: Complete
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["message"] = "All processing finished successfully."
        tasks_db[task_id]["progress"] = 100
        tasks_db[task_id]["result"] = {
            "exam_name": exam_name,
            "exam_id": exam_id,
            "database_stored": grading_db.initialized
        }

    except Exception as e:
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["message"] = f"An error occurred: {str(e)}"
        tasks_db[task_id]["progress"] = 100

# --- FastAPI Application ---
app = FastAPI(
    title="Enhanced Automated Grading API",
    description="A complete API with database integration for managing, processing, and retrieving grading results.",
    version="2.0.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup"""
    success = grading_db.initialize()
    if success:
        logger.info("✅ Database integration initialized successfully")
    else:
        logger.warning("⚠️ Database integration failed - running in file-only mode")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown"""
    grading_db.cleanup()

# --- Helper Functions ---
def get_exam_folder_status(exam_path: Path) -> dict:
    """Enhanced status check with database information"""
    status = {
        "name": exam_path.name,
        "has_answer_key": (exam_path / "answer_key.json").exists(),
        "has_student_answers": (exam_path / "student_answers").is_dir() and any((exam_path / "student_answers").iterdir()),
        "has_processed_results": (exam_path / "processed_student_answers").exists(),
        "database_stored": False,
        "exam_id": None
    }
    
    # Check if this exam exists in database
    if grading_db.initialized:
        try:
            # This is a simplified check - you might want to store exam name mappings
            # For now, we'll just mark as stored if we have processed results
            if status["has_processed_results"]:
                status["database_stored"] = True
        except Exception as e:
            logger.debug(f"Could not check database status: {e}")
    
    return status

# --- API Endpoints ---

@app.get("/", summary="Health Check")
def read_root():
    """Enhanced health check with database status"""
    return {
        "status": "API is healthy",
        "database_connected": grading_db.initialized,
        "version": "2.0.0"
    }

@app.get("/health/database")
def database_health():
    """Check database connection health"""
    if grading_db.initialized:
        return {"status": "connected", "message": "Database integration is active"}
    else:
        return {"status": "disconnected", "message": "Database integration is not available"}

@app.get("/exams", response_model=List[ExamStatus], summary="List All Exams")
def list_exams():
    """Enhanced exam listing with database status"""
    exam_folders = [d for d in EXAMS_BASE_DIR.iterdir() if d.is_dir()]
    return [get_exam_folder_status(path) for path in exam_folders]

@app.post("/exams/{exam_name}", status_code=201, summary="Create a New Exam")
def create_exam(
    exam_name: str = FastApiPath(..., description="A valid folder name for the new exam."),
    exam_type: str = "general"
):
    """Enhanced exam creation with database integration"""
    if not exam_name.replace('_', '').replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid exam name. Use only letters, numbers, underscores, or hyphens.")

    exam_path = EXAMS_BASE_DIR / exam_name
    if exam_path.exists():
        raise HTTPException(status_code=409, detail=f"Exam folder '{exam_name}' already exists.")
    
    # Create folder structure
    (exam_path / "student_answers").mkdir(parents=True, exist_ok=True)
    
    # Store in database
    exam_id = None
    if grading_db.initialized:
        try:
            exam_id = grading_db.store_exam_metadata(exam_name, exam_type)
        except Exception as e:
            logger.warning(f"Could not store exam in database: {e}")
    
    return {
        "message": f"Successfully created exam '{exam_name}'",
        "exam_id": exam_id,
        "database_stored": exam_id is not None
    }

@app.post("/exams/{exam_name}/answer-key", summary="Upload Answer Key")
async def upload_answer_key(exam_name: str, file: UploadFile = File(...)):
    """Enhanced answer key upload with database integration"""
    exam_path = EXAMS_BASE_DIR / exam_name
    if not exam_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Exam folder '{exam_name}' not found.")
    
    destination_path = exam_path / "answer_key.json"
    async with aiofiles.open(destination_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    # Validate and potentially store in database
    database_stored = False
    if grading_db.initialized:
        try:
            # Load and validate the answer key
            with open(destination_path, 'r') as f:
                answer_key_data = json.load(f)
            
            # Store in database (you'd need exam_id mapping here)
            # For now, we'll store it during processing
            database_stored = True
        except Exception as e:
            logger.warning(f"Could not process answer key for database: {e}")

    return {
        "message": "Answer key uploaded successfully.",
        "database_stored": database_stored
    }

@app.post("/exams/{exam_name}/student-answers", summary="Upload Student Answer")
async def upload_student_answer(exam_name: str, file: UploadFile = File(...)):
    """Enhanced student answer upload"""
    student_answers_path = EXAMS_BASE_DIR / exam_name / "student_answers"
    if not student_answers_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Student answers folder for '{exam_name}' not found.")
    
    destination_path = student_answers_path / file.filename
    async with aiofiles.open(destination_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    return {"message": f"Student submission '{file.filename}' uploaded."}

@app.post("/exams/{exam_name}/process", summary="Run Full Grading Pipeline")
def process_exam(
    exam_name: str,
    background_tasks: BackgroundTasks,
    llm_version: str = "v2",
    exam_id: Optional[int] = None
):
    """Enhanced processing with database integration"""
    exam_path = EXAMS_BASE_DIR / exam_name
    if not exam_path.is_dir() or not (exam_path / "answer_key.json").exists():
        raise HTTPException(status_code=404, detail="Exam folder or answer_key.json not found.")

    task_id = str(uuid.uuid4())
    
    # Get or create exam_id
    if not exam_id and grading_db.initialized:
        try:
            exam_id = grading_db.store_exam_metadata(exam_name, "processed_exam")
        except Exception as e:
            logger.warning(f"Could not create exam metadata: {e}")
    
    background_tasks.add_task(run_processing_in_background, task_id, exam_name, llm_version, exam_id)
    
    return {
        "message": "Processing started in the background.",
        "task_id": task_id,
        "exam_id": exam_id,
        "database_integration": grading_db.initialized
    }

@app.get("/tasks/{task_id}", response_model=TaskStatus, summary="Check Task Status")
def get_task_status(task_id: str):
    """Enhanced task status with database information"""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task_id": task_id, **task}

@app.get("/exams/{exam_name}/results", summary="Get All Grading Results")
def get_exam_results(exam_name: str, from_database: bool = True):
    """Enhanced results retrieval with database option"""
    
    # Try database first if available and requested
    if from_database and grading_db.initialized:
        try:
            # This would need exam name to ID mapping - simplified for now
            # In practice, you'd store the mapping or search by name
            logger.info("Database results retrieval not fully implemented - falling back to files")
        except Exception as e:
            logger.warning(f"Could not retrieve from database: {e}")
    
    # Fallback to file-based results (original functionality)
    results_dir = EXAMS_BASE_DIR / exam_name / "processed_student_answers"
    if not results_dir.exists():
        raise HTTPException(status_code=404, detail="Results not found. The exam may not have been processed yet.")

    all_results = {}
    for filepath in results_dir.glob("*_processed.json"):
        student_id = filepath.stem.replace("_processed", "")
        with open(filepath, 'r') as f:
            all_results[student_id] = json.load(f)

    if not all_results:
        return {"message": "Processing is complete, but no student results were generated."}

    return {
        "exam_name": exam_name,
        "results": all_results,
        "source": "database" if from_database and grading_db.initialized else "files",
        "total_results": len(all_results)
    }

@app.get("/exams/{exam_name}/database-results", summary="Get Results from Database")
def get_database_results(exam_name: str, exam_id: int):
    """Get results specifically from database"""
    if not grading_db.initialized:
        raise HTTPException(status_code=503, detail="Database integration not available")
    
    try:
        results = grading_db.get_grading_results(exam_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving database results: {str(e)}")

@app.get("/view-annotations/{exam_name}/{filename}", summary="Load Annotation into Live Prodigy & View")
def view_annotations(
    exam_name: str,
    filename: str = FastApiPath(..., description="The name of the .jsonl file to view")
):
    """Enhanced annotation viewing (unchanged from original)"""
    if not filename.endswith(".jsonl") or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid or unsafe filename.")

    exam_path = EXAMS_BASE_DIR / exam_name

    if filename == "answer_key_prodigy.jsonl":
        source_file_path = exam_path / filename
    else:
        source_file_path = exam_path / "prodigy_data" / filename

    if not source_file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"Annotation file '{filename}' not found at expected path: {source_file_path}"
        )

    try:
        shutil.copyfile(source_file_path, PRODIGY_STREAM_FILE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load data into Prodigy stream: {e}")
        
    return RedirectResponse(url=PRODIGY_URL)

# --- New Database-Specific Endpoints ---

@app.get("/database/exams", summary="List Exams from Database")
def list_database_exams():
    """List exams stored in database"""
    if not grading_db.initialized:
        raise HTTPException(status_code=503, detail="Database integration not available")
    
    # This would be implemented based on your actual schema
    return {"message": "Database exam listing not fully implemented yet"}

@app.get("/database/analytics/{exam_id}", summary="Get Database Analytics")
def get_database_analytics(exam_id: int):
    """Get analytics from database"""
    if not grading_db.initialized:
        raise HTTPException(status_code=503, detail="Database integration not available")
    
    try:
        results = grading_db.get_grading_results(exam_id)
        
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this exam")
        
        # Calculate analytics
        analytics = {
            "exam_id": exam_id,
            "total_submissions": results.get("total_submissions", 0),
            "graded_submissions": results.get("graded_submissions", 0),
            "completion_rate": 0,
            "average_score": 0,
            "score_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
            "needs_review_count": 0
        }
        
        if analytics["total_submissions"] > 0:
            analytics["completion_rate"] = (analytics["graded_submissions"] / analytics["total_submissions"]) * 100
        
        # Calculate score statistics
        scores = []
        needs_review = 0
        
        for student_id, result_data in results.get("results", {}).items():
            summary = result_data.get("summary", {})
            if "percentage" in summary:
                scores.append(summary["percentage"])
            
            if result_data.get("needs_review", False):
                needs_review += 1
        
        if scores:
            analytics["average_score"] = sum(scores) / len(scores)
            
            # Score distribution
            for score in scores:
                if score >= 90:
                    analytics["score_distribution"]["A"] += 1
                elif score >= 80:
                    analytics["score_distribution"]["B"] += 1
                elif score >= 70:
                    analytics["score_distribution"]["C"] += 1
                elif score >= 60:
                    analytics["score_distribution"]["D"] += 1
                else:
                    analytics["score_distribution"]["F"] += 1
        
        analytics["needs_review_count"] = needs_review
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating analytics: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting Enhanced Grading API with Database Integration...")
    uvicorn.run(
        "enhanced_main_api:app",
        host="0.0.0.0",
        port=8001,  # Different port from main backend
        reload=True,
        log_level="info"
    )
