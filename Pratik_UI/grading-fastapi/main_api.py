# main_api.py
import os
import shutil
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Path as FastApiPath
from pydantic import BaseModel
import aiofiles

# Add to the top of main_api.py
from fastapi.responses import RedirectResponse

# --- New Configuration at the top of main_api.py ---
# The static URL where your persistent Prodigy instance is running.
PRODIGY_URL = "http://localhost:8080"
# The file that the persistent Prodigy instance is watching.
PRODIGY_STREAM_FILE = Path("/tmp/prodigy_stream.jsonl")




# --- Configuration ---
# All exam folders will be created inside this base directory.
EXAMS_BASE_DIR = Path("exam_data_storage")
EXAMS_BASE_DIR.mkdir(exist_ok=True)


# --- Pydantic Models for Structured Responses ---
# We use these to define the shape of the data our API returns.
class TaskStatus(BaseModel):
    task_id: str
    status: str  # e.g., "pending", "running", "completed", "failed"
    message: str
    progress: Optional[int] = None
    result: Optional[Any] = None

class ExamStatus(BaseModel):
    name: str
    has_answer_key: bool
    has_student_answers: bool
    has_processed_results: bool


# --- Task Management ---
# A simple in-memory "database" to track the status of background tasks.
# For a production app, you would use a more robust system like Redis.
tasks_db: Dict[str, Dict[str, Any]] = {}


# --- Background Worker Function ---
# This is the function that runs your long, heavy pipeline logic.
def run_processing_in_background(task_id: str, exam_name: str, llm_version: str):
    """
    This function is executed by BackgroundTasks. It imports the correct version
    of your pipeline and runs the processing steps in sequence.
    """
    tasks_db[task_id] = {"status": "running", "message": "Initializing pipeline...", "progress": 0}

    try:
        # Step 1: Dynamically import the correct pipeline version based on user choice.
        tasks_db[task_id]["message"] = f"Loading pipeline version '{llm_version}'..."
        if llm_version == 'v1':
            from main_pipeline.v1.answer_key_processor import process_answer_key
            from main_pipeline.v1.student_processor import process_student_answers
        elif llm_version == 'v2':
            from main_pipeline.v2.answer_key_processor import process_answer_key
            from main_pipeline.v2.student_processor import process_student_answers
        else:
            raise ValueError(f"Invalid pipeline version '{llm_version}' specified.")

        # IMPORTANT: We assume your functions can take the `data_folder` as an argument.
        # You will need to refactor your `process_answer_key` and `process_student_answers`
        # functions to accept the exam folder path.
        exam_folder_path = str(EXAMS_BASE_DIR / exam_name)

        # Step 2: Process the answer key.
        tasks_db[task_id]["progress"] = 10
        tasks_db[task_id]["message"] = "Processing answer key..."
        success_ak = process_answer_key(exam_folder_path)
        if not success_ak:
            raise RuntimeError("Failed to process the answer key.")

        # Step 3: Process the student answers.
        tasks_db[task_id]["progress"] = 50
        tasks_db[task_id]["message"] = "Processing student submissions..."
        success_sa = process_student_answers(exam_folder_path)
        if not success_sa:
            raise RuntimeError("Failed to process student answers.")

        # Step 4: Mark the task as completed.
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["message"] = "All processing finished successfully."
        tasks_db[task_id]["progress"] = 100
        tasks_db[task_id]["result"] = f"Results are available for exam '{exam_name}'."

    except Exception as e:
        # If anything goes wrong, mark the task as failed and record the error.
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["message"] = f"An error occurred: {str(e)}"
        tasks_db[task_id]["progress"] = 100


# --- FastAPI Application ---
app = FastAPI(
    title="Automated Grading API",
    description="A complete API to manage, process, and retrieve grading results.",
)


# --- Helper Function ---
def get_exam_folder_status(exam_path: Path) -> dict:
    """Checks the status of a given exam folder."""
    return {
        "name": exam_path.name,
        "has_answer_key": (exam_path / "answer_key.json").exists(),
        "has_student_answers": (exam_path / "student_answers").is_dir() and any((exam_path / "student_answers").iterdir()),
        "has_processed_results": (exam_path / "processed_student_answers").exists()
    }


# --- API Endpoints ---

@app.get("/", summary="Health Check")
def read_root():
    """Confirms the API is running."""
    return {"status": "API is healthy"}


@app.get("/exams", response_model=List[ExamStatus], summary="List All Exams")
def list_exams():
    """Returns a list of all exam folders and their current status."""
    exam_folders = [d for d in EXAMS_BASE_DIR.iterdir() if d.is_dir()]
    return [get_exam_folder_status(path) for path in exam_folders]


@app.post("/exams/{exam_name}", status_code=201, summary="Create a New Exam")
def create_exam(exam_name: str = FastApiPath(..., description="A valid folder name for the new exam.")):
    """Creates a new directory for an exam and a 'student_answers' subfolder."""
    if not exam_name.isalnum() and '_' not in exam_name and '-' not in exam_name:
         raise HTTPException(status_code=400, detail="Invalid exam name. Use only letters, numbers, underscores, or hyphens.")

    exam_path = EXAMS_BASE_DIR / exam_name
    if exam_path.exists():
        raise HTTPException(status_code=409, detail=f"Exam folder '{exam_name}' already exists.")
    
    (exam_path / "student_answers").mkdir(parents=True, exist_ok=True)
    return {"message": f"Successfully created exam '{exam_name}'"}


@app.post("/exams/{exam_name}/answer-key", summary="Upload Answer Key")
async def upload_answer_key(exam_name: str, file: UploadFile = File(...)):
    """Uploads the 'answer_key.json' file to the specified exam folder."""
    exam_path = EXAMS_BASE_DIR / exam_name
    if not exam_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Exam folder '{exam_name}' not found.")
    
    destination_path = exam_path / "answer_key.json"
    async with aiofiles.open(destination_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    return {"message": "Answer key uploaded successfully."}


@app.post("/exams/{exam_name}/student-answers", summary="Upload Student Answer")
async def upload_student_answer(exam_name: str, file: UploadFile = File(...)):
    """Uploads a student's answer file to the 'student_answers' subfolder."""
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
    llm_version: str = "v2"
):
    """
    Triggers the full grading pipeline in the background for a specific exam.
    This includes processing the answer key and all student submissions.
    """
    exam_path = EXAMS_BASE_DIR / exam_name
    if not exam_path.is_dir() or not (exam_path / "answer_key.json").exists():
        raise HTTPException(status_code=404, detail="Exam folder or answer_key.json not found.")

    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_processing_in_background, task_id, exam_name, llm_version)
    
    return {"message": "Processing started in the background.", "task_id": task_id}


@app.get("/tasks/{task_id}", response_model=TaskStatus, summary="Check Task Status")
def get_task_status(task_id: str):
    """Poll this endpoint with a task_id to check the status of a background job."""
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task_id": task_id, **task}


@app.get("/exams/{exam_name}/results", summary="Get All Grading Results")
def get_exam_results(exam_name: str):
    """Retrieves the aggregated, processed grading results for all students in an exam."""
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

    return {"exam_name": exam_name, "results": all_results}



# --- Add this new endpoint to your API ---

@app.get("/view-annotations/{exam_name}/{filename}", summary="Load Annotation into Live Prodigy & View")
def view_annotations(
    exam_name: str,
    filename: str = FastApiPath(..., description="The name of the .jsonl file to view (e.g., 's1_prodigy.jsonl').")
):
    """
    Loads the content of a specified annotation file into the live,
    running Prodigy instance and redirects the user to it.

    **Pre-requisite:** You must have a Prodigy instance running, which is
    configured to read from the file path specified in PRODIGY_STREAM_FILE.
    """
    # Security check to prevent directory traversal
    if not filename.endswith(".jsonl") or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid or unsafe filename.")

    exam_path = EXAMS_BASE_DIR / exam_name

    # This logic correctly determines where to find the source .jsonl file.
    if filename == "answer_key_prodigy.jsonl":
        # The answer key is in the root of the exam folder.
        source_file_path = exam_path / filename
    else:
        # Student files are in the 'prodigy_data' subfolder.
        source_file_path = exam_path / "prodigy_data" / filename

    # Verify the source file actually exists before we try to copy it.
    if not source_file_path.is_file():
        raise HTTPException(
            status_code=404, 
            detail=f"Annotation file '{filename}' not found at expected path: {source_file_path}"
        )

    try:
        # Core logic: Overwrite the stream file with the content from the source file.
        shutil.copyfile(source_file_path, PRODIGY_STREAM_FILE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load data into Prodigy stream: {e}")
        
    # Redirect the user's browser to the static Prodigy URL.
    return RedirectResponse(url=PRODIGY_URL)