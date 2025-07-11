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

from db_service import DatabaseService, get_db_service
from ocr_code.extract_answer_key import extract_answer_key_to_json
from ocr_code.studentanswer import extract_student_answers_to_json
from grading_wrapper import run_grading_pipeline
from config import SERVER_DATA_DIR

def process_and_download_submissions_v2(course_id: str, coursework_id: str, answer_key_path_str: str, 
                                       service, db_session_maker, grading_version: str = "v2"):
    """
    Updated background task with hybrid database support.
    """
    db = None
    try:
        print(f"BACKGROUND TASK V2: Starting for coursework {coursework_id} with grading version {grading_version}")
        
        # Create database service
        db = db_session_maker()
        db_service = get_db_service(db)
        
        # 1. Extract Answer Key with OCR
        print("BACKGROUND TASK V2: Processing answer key with OCR...")
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        exam_folder_path.mkdir(parents=True, exist_ok=True)
        
        answer_key_json_path = exam_folder_path / "answer_key.json"
        
        try:
            extract_answer_key_to_json(answer_key_path_str, str(answer_key_json_path))
            print(f"BACKGROUND TASK V2: Successfully created answer key JSON at {answer_key_json_path}")
            
            # Store answer key in MongoDB
            with open(answer_key_json_path, 'r') as f:
                answer_key_data = json.load(f)
            
            db_service.store_answer_key(coursework_id, answer_key_data)
            print("BACKGROUND TASK V2: Answer key stored in MongoDB")
            
        except Exception as e:
            print(f"BACKGROUND TASK V2 ERROR: Failed to process answer key. Error: {e}")
            return
        
        # 2. Get or create course and assignment
        try:
            course_info = service.courses().get(id=course_id).execute()
            assignment_info = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
            
            # For migration purposes, use the first user as teacher (you'll need to handle this properly)
            # In a real scenario, you'd get the current user from the session
            teacher_id = uuid.uuid4()  # This should be replaced with actual teacher ID
            
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
                            
                            db_service.store_student_answers(str(submission.id), student_answers)
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
                if task.status in ["PENDING", "RUNNING"] and "specific submissions" in (task.message or "")
            ]
            
            # Only auto-start grading if we have multiple OCR-complete submissions and no individual grading tasks
            if len(ocr_complete_submissions) >= 3 and not individual_grading_tasks:
                print(f"BACKGROUND TASK V2: Found {len(ocr_complete_submissions)} OCR-complete submissions. Starting automatic grading...")
                
                # Check if grading is already in progress
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
            else:
                reason = "individual evaluation mode" if individual_grading_tasks else "insufficient submissions"
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
            from database import SessionLocal
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
