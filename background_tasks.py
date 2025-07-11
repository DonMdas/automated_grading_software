"""
Updated background task functions for the AI Studio application with hybrid database support.
"""

import io
import json
import shutil
import uuid
import traceback
import threading
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials

from db_service import DatabaseService, get_db_service
from database import Submission, Student, Assignment, Course, Exam, User, SessionLocal
from ocr_code.extract_answer_key import extract_answer_key_to_json
from ocr_code.studentanswer import extract_student_answers_to_json
from grading_wrapper import run_grading_pipeline
from config import SERVER_DATA_DIR, SCOPES

def process_and_download_submissions_v2(course_id: str, coursework_id: str, answer_key_path_str: str, 
                                       service, db_session_maker, grading_version: str = "v2", current_user_id: str = None):
    """
    Updated background task with hybrid database support.
    Works with any authenticated user and Google Classroom.
    """
    db = None
    try:
        print(f"BACKGROUND TASK V2: Starting for coursework {coursework_id} with grading version {grading_version}")
        
        # Create database service
        db = db_session_maker()
        db_service = get_db_service(db)
        
        # 1. Extract and Process Answer Key with OCR and Structure Analysis
        print("BACKGROUND TASK V2: Processing answer key with OCR and structure analysis...")
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        exam_folder_path.mkdir(parents=True, exist_ok=True)
        
        answer_key_json_path = exam_folder_path / "answer_key.json"
        answer_key_processed_path = exam_folder_path / "answer_key_processed.json"
        
        try:
            # Step 1: Extract basic answer key with OCR
            extract_answer_key_to_json(answer_key_path_str, str(answer_key_json_path))
            print(f"BACKGROUND TASK V2: Successfully created answer key JSON at {answer_key_json_path}")
            
            # Step 2: Process answer key with structure analysis using grading pipeline
            print("BACKGROUND TASK V2: Processing answer key with structure analysis...")
            from grading_wrapper import GradingPipelineWrapper
            
            wrapper = GradingPipelineWrapper(str(exam_folder_path), version=grading_version)
            
            # Initialize processors
            if wrapper.initialize_processors():
                # Process the answer key to generate structure components
                success = wrapper.process_answer_key(str(exam_folder_path))
                
                if success and answer_key_processed_path.exists():
                    print("BACKGROUND TASK V2: Answer key processed with structure components")
                    
                    # Load the processed answer key with structure components
                    with open(answer_key_processed_path, 'r') as f:
                        answer_key_data = json.load(f)
                    
                    # Store processed answer key in MongoDB
                    db_service.store_answer_key(coursework_id, answer_key_data)
                    print("BACKGROUND TASK V2: Processed answer key stored in MongoDB")
                else:
                    print("BACKGROUND TASK V2: Structure processing failed, using basic answer key")
                    # Fallback to basic answer key
                    with open(answer_key_json_path, 'r') as f:
                        answer_key_data = json.load(f)
                    
                    db_service.store_answer_key(coursework_id, answer_key_data)
                    print("BACKGROUND TASK V2: Basic answer key stored in MongoDB")
            else:
                print("BACKGROUND TASK V2: Failed to initialize grading processors, using basic answer key")
                # Fallback to basic answer key
                with open(answer_key_json_path, 'r') as f:
                    answer_key_data = json.load(f)
                
                db_service.store_answer_key(coursework_id, answer_key_data)
                print("BACKGROUND TASK V2: Basic answer key stored in MongoDB")
            
        except Exception as e:
            print(f"BACKGROUND TASK V2 ERROR: Failed to process answer key. Error: {e}")
            return
        
        # 2. Get or create course and assignment
        try:
            course_info = service.courses().get(id=course_id).execute()
            assignment_info = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
            
            # Use the provided user_id or create a generic one
            teacher_id = current_user_id or str(uuid.uuid4())
            
            course = db_service.get_or_create_course(course_id, course_info, teacher_id)
            assignment = db_service.get_or_create_assignment(coursework_id, course.id, assignment_info)
            exam = db_service.get_or_create_exam(assignment.id, f"Exam for {assignment.title}")
            
        except Exception as e:
            print(f"BACKGROUND TASK V2 ERROR: Failed to setup course/assignment structure: {e}")
            return
        
        # 3. Fetch and Download Student Submissions
        print("BACKGROUND TASK V2: Fetching and downloading student submissions...")
        try:
            submission_results = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id, courseWorkId=coursework_id
            ).execute()
            submissions = submission_results.get('studentSubmissions', [])
            
            if not submissions:
                print("BACKGROUND TASK V2: No submissions found to download.")
                return

            submissions_dir = exam_folder_path / "submissions"
            student_ocr_dir = exam_folder_path / "student_submissions_ocr"
            submissions_dir.mkdir(parents=True, exist_ok=True)
            student_ocr_dir.mkdir(parents=True, exist_ok=True)
            
            drive_service = build('drive', 'v3', credentials=service._http.credentials)

            processed_count = 0
            skipped_count = 0
            total_submissions = len(submissions)
            
            print(f"BACKGROUND TASK V2: Found {total_submissions} total submissions")
            
            for sub in submissions:
                student_id = sub.get('userId')
                submission_state = sub.get('state')
                submission_id = sub.get('id')
                
                print(f"BACKGROUND TASK V2: Processing submission {submission_id} for student {student_id} - state: {submission_state}")
                
                # Skip submissions that are not turned in
                if submission_state != 'TURNED_IN':
                    print(f"BACKGROUND TASK V2: Skipping student {student_id} - submission state: {submission_state}")
                    skipped_count += 1
                    continue
                    
                attachment = sub.get('assignmentSubmission', {}).get('attachments', [])
                if not attachment:
                    print(f"BACKGROUND TASK V2: Skipping student {student_id} - no attachments")
                    skipped_count += 1
                    continue
                    
                drive_file = attachment[0].get('driveFile')
                if not drive_file:
                    print(f"BACKGROUND TASK V2: Skipping student {student_id} - no drive file")
                    skipped_count += 1
                    continue

                file_id = drive_file.get('id')
                original_name = drive_file.get('title', f"file_{file_id}")
                file_extension = Path(original_name).suffix or '.unknown'
                
                local_path = submissions_dir / f"{student_id}{file_extension}"
                
                print(f"BACKGROUND TASK V2: Downloading '{original_name}' for student {student_id}...")
                try:
                    request = drive_service.files().get_media(fileId=file_id)
                    with io.FileIO(local_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done: 
                            _, done = downloader.next_chunk()
                    print(f"BACKGROUND TASK V2: Download complete. File at: {local_path}")
                    
                    # Get student profile
                    try:
                        student_profile = service.userProfiles().get(userId=student_id).execute()
                        student_name = student_profile.get('name', {}).get('fullName', 'Unknown Student')
                    except:
                        student_name = f"Student_{student_id}"
                    
                    # Create or update student and submission records
                    student = db_service.get_or_create_student(
                        student_id, 
                        course.id, 
                        {'name': student_name}
                    )
                    
                    submission = db_service.get_or_create_submission(
                        sub.get('id'),
                        exam.id,
                        assignment.id,
                        student.id,
                        {
                            'google_drive_id': file_id,
                            'local_file_path': str(local_path),
                            'status': 'DOWNLOADED'
                        }
                    )
                    
                    # Process OCR if it's a PDF
                    if local_path.suffix.lower() == '.pdf':
                        print(f"BACKGROUND TASK V2: PDF detected. Processing OCR for student {student_id}...")
                        student_json_path = student_ocr_dir / f"{student_id}.json"
                        try:
                            extract_student_answers_to_json(str(local_path), str(student_json_path))
                            print(f"BACKGROUND TASK V2: Successfully created student OCR JSON at {student_json_path}")
                            
                            # Store student answers in MongoDB
                            with open(student_json_path, 'r') as f:
                                student_answers = json.load(f)
                            
                            try:
                                mongo_id = db_service.store_student_answers(str(submission.id), student_answers)
                                print(f"BACKGROUND TASK V2: Student answers stored/updated in MongoDB with ID: {mongo_id}")
                            except Exception as mongo_e:
                                print(f"BACKGROUND TASK V2 WARNING: Failed to store student answers in MongoDB: {mongo_e}")
                                print("BACKGROUND TASK V2: Continuing with local JSON file...")
                            
                            db_service.update_submission_status(submission.id, "OCR_COMPLETE")
                            
                        except Exception as e:
                            print(f"BACKGROUND TASK V2 ERROR: Failed OCR for student {student_id}. File: {local_path}. Error: {e}")
                            db_service.update_submission_status(submission.id, "OCR_FAILED")
                    else:
                        print(f"BACKGROUND TASK V2: Skipping OCR for non-PDF file: {local_path}")
                        db_service.update_submission_status(submission.id, "DOWNLOADED_NON_PDF")

                    processed_count += 1
                    
                except Exception as e:
                    print(f"BACKGROUND TASK V2 ERROR: Failed to process submission for student {student_id}. Error: {e}")
                    skipped_count += 1
                    continue

            print(f"BACKGROUND TASK V2: Processing complete - {processed_count} processed, {skipped_count} skipped out of {total_submissions} total submissions")

            # 4. Auto-grading after OCR completion
            ocr_complete_submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
            
            # Check if there are any individual grading tasks in progress
            grading_tasks = db_service.get_grading_tasks_by_assignment(coursework_id)
            individual_grading_tasks = [
                task for task in grading_tasks 
                if task.status in ["PENDING", "RUNNING"] and ("specific submissions" in (task.message or "") or "Individual evaluation" in (task.message or ""))
            ]
            
            # Check for stale grading tasks (older than 30 minutes) and mark them as failed
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            stale_tasks = [
                task for task in grading_tasks 
                if task.status in ["PENDING", "RUNNING"] and task.created_at.replace(tzinfo=None) < cutoff_time
            ]
            
            if stale_tasks:
                print(f"BACKGROUND TASK V2: Found {len(stale_tasks)} stale grading tasks, marking as failed...")
                for task in stale_tasks:
                    db_service.update_grading_task(task.id, "FAILED", message="Task timed out and was automatically failed")
                    print(f"BACKGROUND TASK V2: Marked stale task {task.id} as failed")
                # Refresh the grading tasks list after cleanup
                grading_tasks = db_service.get_grading_tasks_by_assignment(coursework_id)
                individual_grading_tasks = [
                    task for task in grading_tasks 
                    if task.status in ["PENDING", "RUNNING"] and ("specific submissions" in (task.message or "") or "Individual evaluation" in (task.message or ""))
                ]
            
            # Only auto-start grading if we have OCR-complete submissions and no individual grading tasks
            if len(ocr_complete_submissions) >= 1 and not individual_grading_tasks:
                print(f"BACKGROUND TASK V2: Found {len(ocr_complete_submissions)} OCR-complete submissions. Starting automatic grading...")
                
                # Check if grading is already in progress (after stale task cleanup)
                existing_task = next(
                    (task for task in grading_tasks if task.status in ["PENDING", "RUNNING"]),
                    None
                )
                
                if not existing_task:
                    # Create new grading task
                    task_id = str(uuid.uuid4())
                    grading_task = db_service.create_grading_task(
                        task_id,
                        assignment.id,
                        grading_version,
                        exam.id
                    )
                    
                    # Start grading immediately
                    print(f"BACKGROUND TASK V2: Starting grading process with version {grading_version}...")
                    process_grading_in_background_v2(task_id, coursework_id, grading_version, db)
                else:
                    print(f"BACKGROUND TASK V2: Grading already in progress, skipping auto-grading")
                    print(f"BACKGROUND TASK V2: Existing task details - ID: {existing_task.id}, Status: {existing_task.status}, Created: {existing_task.created_at}")
            else:
                if individual_grading_tasks:
                    reason = f"individual evaluation mode ({len(individual_grading_tasks)} individual tasks active)"
                    print(f"BACKGROUND TASK V2: Individual grading tasks found:")
                    for task in individual_grading_tasks:
                        print(f"  - Task {task.id}: {task.status} - {task.message}")
                else:
                    reason = f"insufficient submissions (need 1, have {len(ocr_complete_submissions)})"
                print(f"BACKGROUND TASK V2: Found {len(ocr_complete_submissions)} OCR-complete submissions. Skipping auto-grading ({reason})")
        
        except Exception as e:
            print(f"BACKGROUND TASK V2 ERROR in submission processing: {e}")
            traceback.print_exc()
        
    except Exception as e:
        print(f"BACKGROUND TASK V2 FAILED (FATAL): {e}")
        traceback.print_exc()
    finally:
        if db:
            db.close()
        print(f"BACKGROUND TASK V2: Finished for coursework {coursework_id}")

def process_grading_in_background_v2(task_id: str, coursework_id: str, grading_version: str, db: Session = None):
    """
    Updated grading background task with hybrid database support.
    """
    db_service = None
    try:
        print(f"GRADING TASK V2: Starting grading task {task_id} for coursework {coursework_id} with version {grading_version}")
        
        if not db:
            db = SessionLocal()
        
        db_service = get_db_service(db)
        
        # Update task status
        db_service.update_grading_task(task_id, "RUNNING", 5, "Starting grading process...")
        
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        answer_key_json = exam_folder_path / "answer_key.json"
        student_ocr_dir = exam_folder_path / "student_submissions_ocr"
        
        if not answer_key_json.exists():
            raise RuntimeError("Answer key JSON not found. OCR processing may have failed.")
        
        if not student_ocr_dir.exists() or not any(student_ocr_dir.glob("*.json")):
            raise RuntimeError("No student OCR files found. OCR processing may have failed.")
        
        # Create student_answers directory expected by grading pipeline
        student_answers_dir = exam_folder_path / "student_answers"
        student_answers_dir.mkdir(exist_ok=True)
        
        # Copy student OCR files to the expected location
        for ocr_file in student_ocr_dir.glob("*.json"):
            shutil.copy2(ocr_file, student_answers_dir / ocr_file.name)
        
        # Update progress
        db_service.update_grading_task(task_id, progress=10, message=f"Loading grading pipeline version '{grading_version}'...")
        
        print(f"GRADING TASK V2: Running grading pipeline version {grading_version}...")
        
        # Run the grading pipeline
        result = run_grading_pipeline(
            data_folder=str(exam_folder_path),
            version=grading_version
        )
        
        success, message = result
        
        if success:
            # Parse and store grading results
            try:
                grading_results_stored = 0
                prodigy_data_dir = exam_folder_path / "prodigy_data"
                
                if prodigy_data_dir.exists():
                    print(f"GRADING TASK V2: Processing grading results from {prodigy_data_dir}")
                    
                    # Get all submissions for this coursework
                    submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
                    
                    for submission in submissions:
                        student = submission.student
                        if not student:
                            continue
                            
                        # Look for result file for this student
                        result_file = prodigy_data_dir / f"{student.google_student_id}_prodigy.jsonl"
                        
                        if result_file.exists():
                            try:
                                # Parse the JSONL file
                                grading_results = []
                                with open(result_file, 'r') as f:
                                    for line in f:
                                        if line.strip():
                                            grading_results.append(json.loads(line.strip()))
                                
                                # Store in MongoDB
                                mongo_id = db_service.store_grading_results(
                                    str(submission.id), 
                                    {
                                        "results": grading_results,
                                        "grading_version": grading_version,
                                        "total_questions": len(grading_results),
                                        "processed_at": datetime.utcnow().isoformat()
                                    }
                                )
                                
                                # Update submission status to GRADED
                                db_service.update_submission_status(submission.id, "GRADED")
                                grading_results_stored += 1
                                
                                print(f"GRADING TASK V2: Stored results for student {student.google_student_id} (MongoDB ID: {mongo_id})")
                                
                            except Exception as e:
                                print(f"GRADING TASK V2 WARNING: Failed to store results for student {student.google_student_id}: {e}")
                                # Still mark as graded even if MongoDB storage fails
                                db_service.update_submission_status(submission.id, "GRADED")
                        else:
                            print(f"GRADING TASK V2 WARNING: No result file found for student {student.google_student_id}")
                            # Still mark as graded even if no result file
                            db_service.update_submission_status(submission.id, "GRADED")
                
                print(f"GRADING TASK V2: Stored {grading_results_stored} grading results in MongoDB")
                
            except Exception as e:
                print(f"GRADING TASK V2 WARNING: Failed to process grading results: {e}")
                # Still update submission statuses even if result processing fails
                submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
                for submission in submissions:
                    db_service.update_submission_status(submission.id, "GRADED")
            
            # Store result summary
            result_summary = json.dumps({
                "success": True,
                "processed_submissions": len(submissions),
                "grading_version": grading_version,
                "completed_at": datetime.utcnow().isoformat(),
                "message": message,
                "grading_results_stored": grading_results_stored
            })
            
            db_service.update_grading_task(
                task_id, "COMPLETED", 100, 
                f"Grading completed successfully! Processed {len(submissions)} submissions.", 
                result_summary
            )
            
            print(f"GRADING TASK V2: Completed successfully for task {task_id}")
        else:
            db_service.update_grading_task(task_id, "FAILED", message=f"Grading failed: {message}")
            print(f"GRADING TASK V2: Failed for task {task_id}: {message}")
        
    except Exception as e:
        error_msg = f"Grading task failed: {str(e)}"
        print(f"GRADING TASK V2 ERROR: {error_msg}")
        traceback.print_exc()
        
        if db_service:
            db_service.update_grading_task(task_id, "FAILED", message=error_msg)
    
    finally:
        if db_service:
            db_service.close()

def process_specific_submissions(course_id: str, coursework_id: str, answer_key_path_str: str, 
                              service, db_session_maker, student_ids: list, grading_version: str = "v2",
                              user_id: str = None):
    """
    Process only specific submissions identified by student_ids.
    Updated version that works with the new hybrid database schema.
    """
    print(f"BACKGROUND TASK: Starting evaluation for {len(student_ids)} specific submissions in coursework {coursework_id}")
    
    db = db_session_maker()
    db_service = get_db_service(db)
    
    try:
        # Get assignment from database
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        if not assignment:
            print(f"BACKGROUND TASK ERROR: Assignment not found for coursework_id {coursework_id}")
            return
        
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        assignment_dir.mkdir(parents=True, exist_ok=True)
        answer_key_path = Path(answer_key_path_str)
        
        print(f"BACKGROUND TASK: Assignment directory: {assignment_dir}")
        print(f"BACKGROUND TASK: Answer key path: {answer_key_path}")
        print(f"BACKGROUND TASK: Processing students: {student_ids}")
        
        # 1. Process Answer Key with OCR (if not already done)
        print("BACKGROUND TASK: Checking answer key...")
        answer_key_json_path = assignment_dir / "answer_key.json"
        if not answer_key_json_path.exists():
            try:
                print(f"BACKGROUND TASK: Processing answer key PDF: {answer_key_path}")
                extract_answer_key_to_json(str(answer_key_path), str(answer_key_json_path))
                print(f"BACKGROUND TASK: Created answer key JSON at {answer_key_json_path}")
                
                # Store answer key in MongoDB (will update if exists)
                with open(answer_key_json_path, 'r') as f:
                    answer_key_data = json.load(f)
                
                try:
                    exam_id = str(assignment.exams[0].id) if assignment.exams else None
                    if exam_id:
                        mongo_id = db_service.store_answer_key(exam_id, answer_key_data)
                        print(f"BACKGROUND TASK: Answer key stored/updated in MongoDB with ID: {mongo_id}")
                    else:
                        print("BACKGROUND TASK WARNING: No exam found for assignment")
                except Exception as mongo_e:
                    print(f"BACKGROUND TASK WARNING: Failed to store answer key in MongoDB: {mongo_e}")
                    print("BACKGROUND TASK: Continuing with local JSON file...")
                
            except Exception as e:
                print(f"BACKGROUND TASK ERROR: Failed to process answer key. Error: {e}")
                import traceback
                traceback.print_exc()
                return
        else:
            print("BACKGROUND TASK: Answer key JSON already exists")
            # Ensure answer key is also stored in MongoDB
            try:
                with open(answer_key_json_path, 'r') as f:
                    answer_key_data = json.load(f)
                exam_id = str(assignment.exams[0].id) if assignment.exams else None
                if exam_id:
                    mongo_id = db_service.store_answer_key(exam_id, answer_key_data)
                    print(f"BACKGROUND TASK: Answer key ensured in MongoDB with ID: {mongo_id}")
                else:
                    print("BACKGROUND TASK WARNING: No exam found for assignment")
            except Exception as mongo_e:
                print(f"BACKGROUND TASK WARNING: Failed to ensure answer key in MongoDB: {mongo_e}")
                print("BACKGROUND TASK: Continuing with local JSON file...")
        
        # 2. Get submissions from Google Classroom for specific students
        print("BACKGROUND TASK: Fetching submissions from Google Classroom...")
        try:
            submission_results = service.courses().courseWork().studentSubmissions().list(
                courseId=course_id, 
                courseWorkId=coursework_id
            ).execute()
            all_submissions = submission_results.get('studentSubmissions', [])
            print(f"BACKGROUND TASK: Found {len(all_submissions)} total submissions")
            
            # Filter submissions to only include specified student IDs
            target_submissions = [sub for sub in all_submissions if sub.get('userId') in student_ids]
            print(f"BACKGROUND TASK: Filtered to {len(target_submissions)} target submissions")
            
            if not target_submissions:
                print("BACKGROUND TASK: No matching submissions found to process.")
                return
                
        except Exception as e:
            print(f"BACKGROUND TASK ERROR: Failed to fetch submissions from Google Classroom. Error: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 3. Set up Google Drive service using the same credentials as the classroom service
        print("BACKGROUND TASK: Setting up Google Drive service...")
        try:
            # Extract credentials from the classroom service - this works for any authenticated user
            credentials = service._http.credentials
            drive_service = build('drive', 'v3', credentials=credentials)
            print("BACKGROUND TASK: Drive service initialized successfully")
            
        except Exception as e:
            print(f"BACKGROUND TASK ERROR: Failed to setup Drive service. Error: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 4. Download and process each submission
        submissions_dir = assignment_dir / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        
        processed_count = 0
        for sub in target_submissions:
            student_id = sub.get('userId')
            
            try:
                if sub.get('state') != 'TURNED_IN':
                    print(f"BACKGROUND TASK: Skipping student {student_id} - not turned in")
                    continue
                    
                attachment = sub.get('assignmentSubmission', {}).get('attachments', [])
                if not attachment:
                    print(f"BACKGROUND TASK: Skipping student {student_id} - no attachments")
                    continue
                    
                drive_file = attachment[0].get('driveFile')
                if not drive_file:
                    print(f"BACKGROUND TASK: Skipping student {student_id} - no drive file")
                    continue
                
                file_id = drive_file.get('id')
                original_name = drive_file.get('title', f"file_{file_id}")
                file_extension = Path(original_name).suffix or '.pdf'
                local_path = submissions_dir / f"{student_id}{file_extension}"
                
                print(f"BACKGROUND TASK: Processing submission for student {student_id}...")
                
                # Download the file if not already downloaded
                if not local_path.exists():
                    print(f"BACKGROUND TASK: Downloading file for student {student_id}...")
                    request = drive_service.files().get_media(fileId=file_id)
                    with io.FileIO(local_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                    print(f"BACKGROUND TASK: Download complete for student {student_id}")
                else:
                    print(f"BACKGROUND TASK: File already exists for student {student_id}")
                
                # Update database record
                db_submission = db.query(Submission).filter(
                    Submission.assignment_id == assignment.id,
                    Submission.google_submission_id == sub.get('id')
                ).first()
                
                if db_submission:
                    db_submission.local_file_path = str(local_path)
                    db_submission.status = "DOWNLOADED"
                    print(f"BACKGROUND TASK: Updated database record for student {student_id}")
                else:
                    print(f"BACKGROUND TASK: No database record found for student {student_id}")
                
                # Extract student answers using OCR
                try:
                    # Create the student_submissions_ocr directory if it doesn't exist
                    student_ocr_dir = assignment_dir / "student_submissions_ocr"
                    student_ocr_dir.mkdir(exist_ok=True)
                    
                    # Use the correct naming convention and location expected by grading
                    student_answer_json_path = student_ocr_dir / f"{student_id}.json"
                    print(f"BACKGROUND TASK: Extracting answers for student {student_id}...")
                    extract_student_answers_to_json(str(local_path), str(student_answer_json_path))
                    
                    # Store student answers in MongoDB
                    with open(student_answer_json_path, 'r') as f:
                        student_answers = json.load(f)
                    
                    try:
                        mongo_id = db_service.store_student_answers(str(db_submission.id), student_answers)
                        print(f"BACKGROUND TASK V2: Student answers stored/updated in MongoDB with ID: {mongo_id}")
                    except Exception as mongo_e:
                        print(f"BACKGROUND TASK V2 WARNING: Failed to store student answers in MongoDB: {mongo_e}")
                        print("BACKGROUND TASK V2: Continuing with local JSON file...")
                    
                    # Update status to OCR_COMPLETE
                    db_submission.status = "OCR_COMPLETE"
                    print(f"BACKGROUND TASK: OCR complete for student {student_id}")
                    
                except Exception as e:
                    print(f"BACKGROUND TASK V2 ERROR: Failed OCR for student {student_id}. File: {local_path}. Error: {e}")
                    db_submission.status = "OCR_FAILED"
                
                db.commit()
                processed_count += 1
                
            except Exception as e:
                print(f"BACKGROUND TASK ERROR: Failed to process student {student_id}. Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"BACKGROUND TASK: Processed {processed_count} specific submissions")
        
        # 4. Start grading for OCR-complete submissions
        if processed_count > 0:
            print("BACKGROUND TASK: Starting individual grading process...")
            print(f"BACKGROUND TASK: Creating grading task for {len(student_ids)} students: {student_ids}")
            
            # Create a grading task for specific submissions
            task_id = str(uuid.uuid4())
            # Update the task message to indicate individual evaluation
            grading_task = db_service.create_grading_task(
                task_id=task_id,
                assignment_id=assignment.id,
                grading_version=grading_version,
                exam_id=assignment.exams[0].id if assignment.exams else None
            )
            # Update task message to indicate individual evaluation
            db_service.update_grading_task(task_id, "PENDING", 0, f"Individual evaluation for specific submissions: {student_ids}")
            print(f"BACKGROUND TASK: Created grading task {task_id}")
            
            # Run grading for specific students only
            print(f"BACKGROUND TASK: Starting individual grading background task...")
            # Run in a separate thread to avoid blocking
            grading_thread = threading.Thread(
                target=process_individual_grading_in_background,
                args=(task_id, coursework_id, student_ids, grading_version, None)  # Pass None for db to create fresh session
            )
            grading_thread.start()
            print(f"BACKGROUND TASK: Individual grading thread started for task {task_id}")
        
        print(f"BACKGROUND TASK: Completed processing {processed_count} specific submissions")
        
    except Exception as e:
        print(f"BACKGROUND TASK FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.close()

def process_individual_grading_in_background(task_id: str, coursework_id: str, student_ids: list, grading_version: str, db: Session = None):
    """
    Individual grading background task - only processes specific students.
    """
    db_service = None
    print(f"INDIVIDUAL GRADING TASK: ENTRY POINT - Starting grading task {task_id}")
    print(f"INDIVIDUAL GRADING TASK: Students to process: {student_ids}")
    print(f"INDIVIDUAL GRADING TASK: Coursework ID: {coursework_id}")
    print(f"INDIVIDUAL GRADING TASK: Grading version: {grading_version}")
    
    try:
        print(f"INDIVIDUAL GRADING TASK: Starting grading task {task_id} for specific students {student_ids} in coursework {coursework_id} with version {grading_version}")
        
        if not db:
            db = SessionLocal()
            print(f"INDIVIDUAL GRADING TASK: Created fresh database session")
        
        db_service = get_db_service(db)
        print(f"INDIVIDUAL GRADING TASK: Got database service")
        
        # Update task status
        db_service.update_grading_task(task_id, "RUNNING", 5, f"Starting individual grading for {len(student_ids)} specific submissions...")
        print(f"INDIVIDUAL GRADING TASK: Updated task status to RUNNING")
        
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        answer_key_json = exam_folder_path / "answer_key.json"
        student_ocr_dir = exam_folder_path / "student_submissions_ocr"
        
        if not answer_key_json.exists():
            raise RuntimeError("Answer key JSON not found. OCR processing may have failed.")
        
        if not student_ocr_dir.exists():
            # Try to create the directory and trigger OCR processing
            print(f"INDIVIDUAL GRADING TASK: Student OCR directory not found. Creating and triggering OCR processing...")
            student_ocr_dir.mkdir(parents=True, exist_ok=True)
            
            # Get assignment and trigger OCR for pending submissions
            assignment = db.query(Assignment).filter(
                Assignment.google_assignment_id == coursework_id
            ).first()
            
            if assignment:
                pending_submissions = db.query(Submission).filter(
                    Submission.assignment_id == assignment.id,
                    Submission.status.in_(["PENDING", "DOWNLOADED"])
                ).all()
                
                if pending_submissions:
                    print(f"INDIVIDUAL GRADING TASK: Found {len(pending_submissions)} submissions that need OCR processing")
                    # We'll continue with the ones that have OCR files and warn about the missing ones
                else:
                    print(f"INDIVIDUAL GRADING TASK: No pending submissions found for OCR processing")
            else:
                print(f"INDIVIDUAL GRADING TASK: Assignment not found for coursework {coursework_id}")
        
        # Check if specific student OCR files exist
        student_ocr_files = []
        missing_ocr_students = []
        
        for student_id in student_ids:
            # First check the correct location and naming
            ocr_file = student_ocr_dir / f"{student_id}.json"
            
            # If not found, check for legacy naming pattern
            if not ocr_file.exists():
                legacy_ocr_file = exam_folder_path / f"student_answers_{student_id}.json"
                if legacy_ocr_file.exists():
                    print(f"INDIVIDUAL GRADING TASK: Found legacy OCR file for student {student_id}, moving to correct location")
                    # Move the file to the correct location with correct naming
                    try:
                        student_ocr_dir.mkdir(exist_ok=True)
                        legacy_ocr_file.rename(ocr_file)
                        print(f"INDIVIDUAL GRADING TASK: Moved {legacy_ocr_file} to {ocr_file}")
                    except Exception as move_error:
                        print(f"INDIVIDUAL GRADING TASK: Failed to move legacy file: {move_error}")
                        # If move fails, try to copy
                        try:
                            shutil.copy2(legacy_ocr_file, ocr_file)
                            print(f"INDIVIDUAL GRADING TASK: Copied {legacy_ocr_file} to {ocr_file}")
                        except Exception as copy_error:
                            print(f"INDIVIDUAL GRADING TASK: Failed to copy legacy file: {copy_error}")
            
            if ocr_file.exists():
                student_ocr_files.append(ocr_file)
            else:
                missing_ocr_students.append(student_id)
                print(f"INDIVIDUAL GRADING TASK WARNING: OCR file not found for student {student_id}")
                print(f"INDIVIDUAL GRADING TASK WARNING: Checked {ocr_file}")
                print(f"INDIVIDUAL GRADING TASK WARNING: Also checked legacy location {exam_folder_path / f'student_answers_{student_id}.json'}")
        
        if not student_ocr_files:
            error_msg = f"No OCR files found for specified students: {student_ids}. "
            if missing_ocr_students:
                error_msg += f"Missing OCR files for: {missing_ocr_students}. "
            error_msg += "Please ensure submissions are loaded and OCR processing is complete."
            raise RuntimeError(error_msg)
        
        if missing_ocr_students:
            print(f"INDIVIDUAL GRADING TASK: Proceeding with {len(student_ocr_files)} students that have OCR files")
            print(f"INDIVIDUAL GRADING TASK: Missing OCR files for: {missing_ocr_students}")
            # Update the task with a warning but continue
            db_service.update_grading_task(task_id, progress=5, message=f"Warning: Missing OCR files for {len(missing_ocr_students)} students. Proceeding with {len(student_ocr_files)} students...")
        
        # Create student_answers directory expected by grading pipeline
        student_answers_dir = exam_folder_path / "student_answers"
        
        # Clean up any existing files to ensure only specific students are processed
        if student_answers_dir.exists():
            shutil.rmtree(student_answers_dir)
            print(f"INDIVIDUAL GRADING TASK: Cleaned up existing student_answers directory")
        
        student_answers_dir.mkdir(exist_ok=True)
        
        # Copy only the specific student OCR files to the expected location
        for ocr_file in student_ocr_files:
            shutil.copy2(ocr_file, student_answers_dir / ocr_file.name)
            print(f"INDIVIDUAL GRADING TASK: Copied OCR file for student {ocr_file.stem}")
        
        print(f"INDIVIDUAL GRADING TASK: Prepared {len(student_ocr_files)} student files for individual grading")
        
        # Clean up any existing grading results to avoid confusion
        prodigy_data_dir = exam_folder_path / "prodigy_data"
        if prodigy_data_dir.exists():
            shutil.rmtree(prodigy_data_dir)
            print(f"INDIVIDUAL GRADING TASK: Cleaned up existing grading results directory")
        
        # Update progress
        db_service.update_grading_task(task_id, progress=10, message=f"Loading grading pipeline version '{grading_version}' for individual evaluation...")
        
        print(f"INDIVIDUAL GRADING TASK: Running grading pipeline version {grading_version} for {len(student_ocr_files)} students...")
        
        # Run the grading pipeline
        result = run_grading_pipeline(
            data_folder=str(exam_folder_path),
            version=grading_version
        )
        
        success, message = result
        
        if success:
            # Parse and store grading results for specific students only
            try:
                grading_results_stored = 0
                prodigy_data_dir = exam_folder_path / "prodigy_data"
                
                if prodigy_data_dir.exists():
                    print(f"INDIVIDUAL GRADING TASK: Processing grading results from {prodigy_data_dir}")
                    
                    # List all result files to see what was actually generated
                    result_files = list(prodigy_data_dir.glob("*_prodigy.jsonl"))
                    print(f"INDIVIDUAL GRADING TASK: Found {len(result_files)} result files: {[f.name for f in result_files]}")
                    
                    # Get submissions for specific students only
                    submissions = []
                    for student_id in student_ids:
                        student_submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
                        for submission in student_submissions:
                            if submission.student and submission.student.google_student_id == student_id:
                                submissions.append(submission)
                                print(f"INDIVIDUAL GRADING TASK: Found submission for student {student_id}")
                                break
                    
                    print(f"INDIVIDUAL GRADING TASK: Processing results for {len(submissions)} specific submissions")
                    
                    for submission in submissions:
                        student = submission.student
                        if not student:
                            continue
                            
                        # Look for result file for this student
                        result_file = prodigy_data_dir / f"{student.google_student_id}_prodigy.jsonl"
                        
                        # Verify this student was in our target list (double-check for safety)
                        if student.google_student_id not in student_ids:
                            print(f"INDIVIDUAL GRADING TASK WARNING: Skipping unexpected result for student {student.google_student_id}")
                            continue
                        
                        print(f"INDIVIDUAL GRADING TASK: Processing result file for target student {student.google_student_id}")
                        
                        if result_file.exists():
                            try:
                                # Parse the JSONL file
                                grading_results = []
                                with open(result_file, 'r') as f:
                                    for line in f:
                                        if line.strip():
                                            grading_results.append(json.loads(line.strip()))
                                
                                # Store in MongoDB
                                mongo_id = db_service.store_grading_results(
                                    str(submission.id), 
                                    {
                                        "results": grading_results,
                                        "grading_version": grading_version,
                                        "total_questions": len(grading_results),
                                        "processed_at": datetime.utcnow().isoformat(),
                                        "evaluation_type": "individual"
                                    }
                                )
                                
                                # Update submission status to GRADED
                                db_service.update_submission_status(submission.id, "GRADED")
                                grading_results_stored += 1
                                
                                print(f"INDIVIDUAL GRADING TASK: Stored results for student {student.google_student_id} (MongoDB ID: {mongo_id})")
                                
                            except Exception as e:
                                print(f"INDIVIDUAL GRADING TASK WARNING: Failed to store results for student {student.google_student_id}: {e}")
                                # Still mark as graded even if MongoDB storage fails
                                db_service.update_submission_status(submission.id, "GRADED")
                        else:
                            print(f"INDIVIDUAL GRADING TASK WARNING: No result file found for student {student.google_student_id}")
                            # Still mark as graded even if no result file
                            db_service.update_submission_status(submission.id, "GRADED")
                
                print(f"INDIVIDUAL GRADING TASK: Stored {grading_results_stored} grading results in MongoDB")
                
            except Exception as e:
                print(f"INDIVIDUAL GRADING TASK WARNING: Failed to process grading results: {e}")
                # Still update submission statuses even if result processing fails
                for student_id in student_ids:
                    student_submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
                    for submission in student_submissions:
                        if submission.student and submission.student.google_student_id == student_id:
                            db_service.update_submission_status(submission.id, "GRADED")
                            break
            
            # Store result summary
            result_summary = json.dumps({
                "success": True,
                "processed_submissions": len(submissions),
                "grading_version": grading_version,
                "completed_at": datetime.utcnow().isoformat(),
                "message": message,
                "grading_results_stored": grading_results_stored,
                "evaluation_type": "individual",
                "student_ids": student_ids
            })
            
            db_service.update_grading_task(
                task_id, "COMPLETED", 100, 
                f"Individual grading completed successfully! Processed {len(submissions)} specific submissions.", 
                result_summary
            )
            
            print(f"INDIVIDUAL GRADING TASK: Completed successfully for task {task_id}")
        else:
            db_service.update_grading_task(task_id, "FAILED", message=f"Individual grading failed: {message}")
            print(f"INDIVIDUAL GRADING TASK: Failed for task {task_id}: {message}")
        
    except Exception as e:
        error_msg = f"Individual grading task failed: {str(e)}"
        print(f"INDIVIDUAL GRADING TASK ERROR: {error_msg}")
        traceback.print_exc()
        
        if db_service:
            db_service.update_grading_task(task_id, "FAILED", message=error_msg)
    
    finally:
        if db_service:
            db_service.close()
        
        # Clean up: remove the student_answers directory to avoid affecting future bulk evaluations
        try:
            student_answers_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}") / "student_answers"
            if student_answers_dir.exists():
                shutil.rmtree(student_answers_dir)
                print(f"INDIVIDUAL GRADING TASK: Cleaned up temporary student_answers directory")
        except Exception as cleanup_e:
            print(f"INDIVIDUAL GRADING TASK WARNING: Failed to clean up student_answers directory: {cleanup_e}")

# Legacy compatibility wrapper
def process_and_download_submissions(course_id: str, coursework_id: str, answer_key_path_str: str, 
                                   service, db_session_maker, grading_version: str = "v2"):
    """Legacy compatibility wrapper"""
    return process_and_download_submissions_v2(
        course_id, coursework_id, answer_key_path_str, service, db_session_maker, grading_version
    )

def process_grading_in_background(task_id: str, coursework_id: str, grading_version: str, db: Session = None):
    """Legacy compatibility wrapper"""
    return process_grading_in_background_v2(task_id, coursework_id, grading_version, db)
