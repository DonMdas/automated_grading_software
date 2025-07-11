"""
Background task functions for the AI Studio application.
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

from database import (
    Assignment, Student, Submission, Exam, GradingTask, SessionLocal, Course, mongo_manager
)
from ocr_code.extract_answer_key import extract_answer_key_to_json
from ocr_code.studentanswer import extract_student_answers_to_json
from grading_wrapper import run_grading_pipeline
from config import SERVER_DATA_DIR

def process_and_download_submissions(course_id: str, coursework_id: str, answer_key_path_str: str, service, db_session_maker, grading_version: str = "v2"):
    """
    Background task with proper database session management.
    """
    print(f"BACKGROUND TASK: Starting evaluation process for coursework {coursework_id}")
    
    # Create a new database session for this background task
    db = db_session_maker()
    
    try:
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        answer_key_path = Path(answer_key_path_str)
        
        # 1. Process Answer Key with OCR
        print("BACKGROUND TASK: Processing answer key with OCR...")
        answer_key_json_path = assignment_dir / "answer_key.json"
        try:
            extract_answer_key_to_json(str(answer_key_path), str(answer_key_json_path))
            print(f"BACKGROUND TASK: Successfully created answer key JSON at {answer_key_json_path}")
        except Exception as e:
            print(f"BACKGROUND TASK ERROR: Failed to process answer key with OCR. Error: {e}")
            # Continue with submission downloads even if answer key OCR fails
    
        # 2. Fetch and Download Student Submissions
        print("BACKGROUND TASK: Fetching and downloading student submissions...")
        try:
            coursework_details = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
            assignment_name = coursework_details.get('title', 'Unknown Assignment')

            db_assignment = db.query(Assignment).filter(Assignment.google_id == coursework_id).first()
            if not db_assignment:
                db_assignment = Assignment(google_id=coursework_id, name=assignment_name)
                db.add(db_assignment)
                db.commit()

            submission_results = service.courses().courseWork().studentSubmissions().list(courseId=course_id, courseWorkId=coursework_id).execute()
            submissions = submission_results.get('studentSubmissions', [])
            if not submissions:
                print("BACKGROUND TASK: No submissions found to download.")
                return

            submissions_dir = assignment_dir / "submissions"
            student_ocr_dir = assignment_dir / "student_submissions_ocr"
            submissions_dir.mkdir(parents=True, exist_ok=True)
            student_ocr_dir.mkdir(parents=True, exist_ok=True)
            
            drive_service = build('drive', 'v3', credentials=service._http.credentials)

            processed_count = 0
            skipped_count = 0
            total_submissions = len(submissions)
            
            print(f"BACKGROUND TASK: Found {total_submissions} total submissions")
            
            for sub in submissions:
                student_id = sub.get('userId')
                submission_state = sub.get('state')
                
                # Skip submissions that are not turned in
                if submission_state != 'TURNED_IN':
                    print(f"BACKGROUND TASK: Skipping student {student_id} - submission state: {submission_state}")
                    skipped_count += 1
                    continue
                    
                attachment = sub.get('assignmentSubmission', {}).get('attachments', [])
                if not attachment:
                    print(f"BACKGROUND TASK: Skipping student {student_id} - no attachments")
                    skipped_count += 1
                    continue
                    
                drive_file = attachment[0].get('driveFile')
                if not drive_file:
                    print(f"BACKGROUND TASK: Skipping student {student_id} - no drive file")
                    skipped_count += 1
                    continue

                file_id = drive_file.get('id')
                original_name = drive_file.get('title', f"file_{file_id}")
                file_extension = Path(original_name).suffix or '.unknown'
                student_id = sub.get('userId')
                
                local_path = submissions_dir / f"{student_id}{file_extension}"
                
                print(f"BACKGROUND TASK: Downloading '{original_name}' for student {student_id}...")
                try:
                    request = drive_service.files().get_media(fileId=file_id)
                    with io.FileIO(local_path, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while not done: 
                            _, done = downloader.next_chunk()
                    print(f"BACKGROUND TASK: Download complete. File at: {local_path}")
                    
                    # Get student profile
                    try:
                        student_profile = service.userProfiles().get(userId=student_id).execute()
                        student_name = student_profile.get('name', {}).get('fullName', 'Unknown Student')
                    except:
                        student_name = f"Student_{student_id}"
                    
                    # Update database records
                    db_student = db.query(Student).filter(Student.google_id == student_id).first()
                    if not db_student:
                        db_student = Student(google_id=student_id, name=student_name)
                        db.add(db_student)
                        db.commit()

                    db_submission = db.query(SubmissionRecord).filter(SubmissionRecord.google_submission_id == sub.get('id')).first()
                    if not db_submission:
                        db_submission = SubmissionRecord(
                            google_submission_id=sub.get('id'), 
                            course_id=course_id, 
                            coursework_id=coursework_id,
                            student_id=student_id, 
                            student_name=student_name, 
                            google_drive_id=file_id,
                            local_file_path=str(local_path),
                            status="DOWNLOADED"
                        )
                        db.add(db_submission)
                    else: 
                        db_submission.local_file_path = str(local_path)
                        db_submission.status = "DOWNLOADED"
                    
                    # 3. Process each student submission with OCR (if it's a PDF)
                    if local_path.suffix.lower() == '.pdf':
                        print(f"BACKGROUND TASK: PDF detected. Processing OCR for student {student_id}...")
                        student_json_path = student_ocr_dir / f"{student_id}.json"
                        try:
                            extract_student_answers_to_json(str(local_path), str(student_json_path))
                            print(f"BACKGROUND TASK: Successfully created student OCR JSON at {student_json_path}")
                            db_submission.status = "OCR_COMPLETE"
                        except Exception as e:
                            print(f"BACKGROUND TASK ERROR: Failed OCR for student {student_id}. File: {local_path}. Error: {e}")
                            db_submission.status = "OCR_FAILED"
                    else:
                        print(f"BACKGROUND TASK: Skipping OCR for non-PDF file: {local_path}")
                        db_submission.status = "DOWNLOADED_NON_PDF"

                    db.commit()
                    processed_count += 1
                    
                except Exception as e:
                    print(f"BACKGROUND TASK ERROR: Failed to process submission for student {student_id}. Error: {e}")
                    skipped_count += 1
                    continue

            print(f"BACKGROUND TASK: Processing complete - {processed_count} processed, {skipped_count} skipped out of {total_submissions} total submissions")

            # 4. Auto-grading after OCR completion with individual evaluation protection
            # Only run auto-grading if there are multiple new OCR-complete submissions
            # and no individual evaluation is in progress
            ocr_complete_submissions = db.query(SubmissionRecord).filter(
                SubmissionRecord.coursework_id == coursework_id,
                SubmissionRecord.status == "OCR_COMPLETE"
            ).all()
            
            # Check if there are any individual grading tasks in progress
            individual_grading_tasks = db.query(GradingTask).filter(
                GradingTask.coursework_id == coursework_id,
                GradingTask.status.in_(["PENDING", "RUNNING"]),
                GradingTask.message.contains("specific submissions")
            ).all()
            
            # Only auto-start grading if:
            # 1. We have multiple OCR-complete submissions (bulk processing)
            # 2. No individual grading tasks are in progress
            # 3. No general grading tasks are already running
            if len(ocr_complete_submissions) >= 3 and not individual_grading_tasks:
                print(f"BACKGROUND TASK: Found {len(ocr_complete_submissions)} OCR-complete submissions. Starting automatic grading...")
                
                # Check if grading is already in progress
                existing_task = db.query(GradingTask).filter(
                    GradingTask.coursework_id == coursework_id,
                    GradingTask.status.in_(["PENDING", "RUNNING"])
                ).first()
                
                if not existing_task:
                    # Create new grading task
                    task_id = str(uuid.uuid4())
                    grading_task = GradingTask(
                        task_id=task_id,
                        coursework_id=coursework_id,
                        grading_version=grading_version,  # Use the provided grading version
                        status="PENDING",
                        message="Auto-grading task created after OCR completion..."
                    )
                    db.add(grading_task)
                    db.commit()
                    
                    # Start grading immediately (not as background task since we're already in one)
                    print(f"BACKGROUND TASK: Starting grading process with version {grading_version}...")
                    process_grading_in_background(task_id, coursework_id, grading_version, db)
                else:
                    print(f"BACKGROUND TASK: Grading already in progress, skipping auto-grading")
            else:
                reason = "individual evaluation mode" if individual_grading_tasks else "insufficient submissions"
                print(f"BACKGROUND TASK: Found {len(ocr_complete_submissions)} OCR-complete submissions. Skipping auto-grading ({reason})")
        
        except Exception as e:
            print(f"BACKGROUND TASK ERROR in submission processing: {e}")
            traceback.print_exc()
        
        except Exception as e:
            print(f"BACKGROUND TASK ERROR in submission processing: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"BACKGROUND TASK FAILED (FATAL): {e}")
        traceback.print_exc()
    finally:
        db.close()
        print(f"BACKGROUND TASK: Finished for coursework {coursework_id}")

def process_grading_in_background(task_id: str, coursework_id: str, grading_version: str, db: Session = None):
    """
    Background task to run the grading pipeline after OCR is complete.
    This function is executed by BackgroundTasks and runs the grading process.
    """
    print(f"GRADING TASK: Starting grading process for coursework {coursework_id} with version {grading_version}")
    
    # Create a new database session if not provided
    if db is None:
        db = SessionLocal()
    
    try:
        # Update task status in database
        grading_task = db.query(GradingTask).filter(GradingTask.task_id == task_id).first()
        if grading_task:
            grading_task.status = "RUNNING"
            grading_task.message = "Initializing grading pipeline..."
            grading_task.progress = 0
            db.commit()
    
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        
        # Check if required files exist
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
        if grading_task:
            grading_task.progress = 10
            grading_task.message = f"Loading grading pipeline version '{grading_version}'..."
            db.commit()
        
        print(f"GRADING TASK: Running grading pipeline version {grading_version}...")
        success, message = run_grading_pipeline(str(exam_folder_path), grading_version)
        
        if not success:
            raise RuntimeError(f"Grading pipeline failed: {message}")
        
        print(f"GRADING TASK: {message}")
        
        # Update progress
        if grading_task:
            grading_task.progress = 70
            grading_task.message = "Grading pipeline completed, updating records..."
            db.commit()
        
        # Update submission records in database
        if grading_task:
            grading_task.progress = 80
            grading_task.message = "Updating submission records..."
            db.commit()
        
        # Mark individual submissions as graded
        submissions = db.query(SubmissionRecord).filter(
            SubmissionRecord.coursework_id == coursework_id,
            SubmissionRecord.status == "OCR_COMPLETE"
        ).all()
        
        graded_count = 0
        for submission in submissions:
            # Check if grading result exists for this student
            prodigy_data_dir = exam_folder_path / "prodigy_data"
            student_result_file = prodigy_data_dir / f"{submission.student_id}_prodigy.jsonl"
            
            if student_result_file.exists():
                submission.status = "GRADED"
                graded_count += 1
                print(f"GRADING TASK: Marked submission for student {submission.student_id} as GRADED")
            else:
                submission.status = "GRADING_FAILED"
                print(f"GRADING TASK: Marked submission for student {submission.student_id} as GRADING_FAILED")
        
        # Also check if any submissions marked as GRADED still have their result files
        # This prevents already-graded submissions from being incorrectly marked as failed
        already_graded_submissions = db.query(SubmissionRecord).filter(
            SubmissionRecord.coursework_id == coursework_id,
            SubmissionRecord.status == "GRADED"
        ).all()
        
        for submission in already_graded_submissions:
            # Check if grading result still exists for this student
            prodigy_data_dir = exam_folder_path / "prodigy_data"
            student_result_file = prodigy_data_dir / f"{submission.student_id}_prodigy.jsonl"
            
            if not student_result_file.exists():
                submission.status = "GRADING_FAILED"
                print(f"GRADING TASK: Marked previously graded submission for student {submission.student_id} as GRADING_FAILED (result file missing)")
            else:
                print(f"GRADING TASK: Confirmed submission for student {submission.student_id} remains GRADED (result file exists)")
        
        db.commit()
        
        # Mark the grading task as completed
        if grading_task:
            grading_task.status = "COMPLETED"
            grading_task.message = f"Grading process completed successfully. {graded_count} submissions graded."
            grading_task.progress = 100
            grading_task.completed_at = datetime.utcnow()
            grading_task.result = json.dumps({
                "message": f"Grading completed for coursework {coursework_id}",
                "graded_submissions": graded_count,
                "total_submissions": len(submissions)
            })
            db.commit()
        
        print(f"GRADING TASK: Completed successfully for coursework {coursework_id}. {graded_count} submissions graded.")
        
    except Exception as e:
        print(f"GRADING TASK FAILED: {e}")
        if grading_task:
            grading_task.status = "FAILED"
            grading_task.message = f"Grading failed: {str(e)}"
            grading_task.progress = 100
            grading_task.completed_at = datetime.utcnow()
            db.commit()
    finally:
        if db:
            db.close()
        print(f"GRADING TASK: Finished for coursework {coursework_id}")

def process_specific_submissions(course_id: str, coursework_id: str, answer_key_path_str: str, service, db_session_maker, student_ids: list, grading_version: str = "v2"):
    """
    Process only specific submissions identified by student_ids.
    This is more efficient than processing all submissions when only a few need grading.
    """
    print(f"BACKGROUND TASK: Starting evaluation for {len(student_ids)} specific submissions in coursework {coursework_id}")
    
    # Create a new database session for this background task
    db = db_session_maker()
    
    try:
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
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
                from ocr_code.extract_answer_key import extract_answer_key_to_json
                extract_answer_key_to_json(str(answer_key_path), str(answer_key_json_path))
                print(f"BACKGROUND TASK: Created answer key JSON at {answer_key_json_path}")
            except Exception as e:
                print(f"BACKGROUND TASK ERROR: Failed to process answer key. Error: {e}")
                import traceback
                traceback.print_exc()
                return
        else:
            print("BACKGROUND TASK: Answer key JSON already exists")
        
        # Get assignment from database
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        if not assignment:
            print(f"BACKGROUND TASK ERROR: Assignment not found for coursework_id {coursework_id}")
            return
            
        print(f"BACKGROUND TASK: Found assignment: {assignment.title}")
        
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
        
        submissions_dir = assignment_dir / "submissions"
        student_ocr_dir = assignment_dir / "student_submissions_ocr"
        submissions_dir.mkdir(parents=True, exist_ok=True)
        student_ocr_dir.mkdir(parents=True, exist_ok=True)
        
        from googleapiclient.discovery import build
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        try:
            drive_service = build('drive', 'v3', credentials=service._http.credentials)
        except Exception as e:
            print(f"BACKGROUND TASK ERROR: Failed to build drive service. Error: {e}")
            import traceback
            traceback.print_exc()
            return
        
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
                file_extension = Path(original_name).suffix or '.unknown'
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
                
                # Process with OCR if it's a PDF
                if local_path.suffix.lower() == '.pdf':
                    print(f"BACKGROUND TASK: Processing OCR for student {student_id}...")
                    student_json_path = student_ocr_dir / f"{student_id}.json"
                    
                    try:
                        from ocr_code.studentanswer import extract_student_answers_to_json
                        extract_student_answers_to_json(str(local_path), str(student_json_path))
                        print(f"BACKGROUND TASK: OCR complete for student {student_id}")
                        if db_submission:
                            db_submission.status = "OCR_COMPLETE"
                    except Exception as e:
                        print(f"BACKGROUND TASK ERROR: OCR failed for student {student_id}. Error: {e}")
                        import traceback
                        traceback.print_exc()
                        if db_submission:
                            db_submission.status = "OCR_FAILED"
                else:
                    print(f"BACKGROUND TASK: Skipping OCR for non-PDF file: {local_path}")
                    if db_submission:
                        db_submission.status = "DOWNLOADED_NON_PDF"
                
                db.commit()
                processed_count += 1
                
            except Exception as e:
                print(f"BACKGROUND TASK ERROR: Failed to process student {student_id}. Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"BACKGROUND TASK: Processed {processed_count} specific submissions")
        
        # 3. Start grading for OCR-complete submissions
        ocr_complete_submissions = db.query(SubmissionRecord).filter(
            SubmissionRecord.coursework_id == coursework_id,
            SubmissionRecord.student_id.in_(student_ids),
            SubmissionRecord.status == "OCR_COMPLETE"
        ).all()
        
        if ocr_complete_submissions:
            print(f"BACKGROUND TASK: Starting grading for {len(ocr_complete_submissions)} submissions...")
            
            import uuid
            from database import GradingTask
            
            # Create grading task
            task_id = str(uuid.uuid4())
            grading_task = GradingTask(
                task_id=task_id,
                coursework_id=coursework_id,
                grading_version=grading_version,  # Use the provided grading version
                status="PENDING",
                message=f"Grading specific submissions for {len(student_ids)} students..."
            )
            db.add(grading_task)
            db.commit()
            
            # Run grading in background for specific students only
            try:
                # Start the specific grading process in a separate thread to avoid blocking
                import threading
                grading_thread = threading.Thread(
                    target=process_specific_grading,
                    args=(task_id, coursework_id, grading_version, student_ids, db_session_maker)  # Pass grading version
                )
                grading_thread.start()
                print(f"BACKGROUND TASK: Successfully started grading thread for {len(ocr_complete_submissions)} submissions")
            except Exception as e:
                print(f"BACKGROUND TASK ERROR: Failed to start grading process. Error: {e}")
                import traceback
                traceback.print_exc()
                # Update task status to failed
                grading_task.status = "FAILED"
                grading_task.message = f"Failed to start grading: {str(e)}"
                db.commit()
            
        else:
            print("BACKGROUND TASK: No OCR-complete submissions found for grading")
            
    except Exception as e:
        print(f"BACKGROUND TASK FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.close()
            print(f"BACKGROUND TASK: Database connection closed for coursework {coursework_id}")

def process_specific_grading(task_id: str, coursework_id: str, grading_version: str, student_ids: list, db_session_maker):
    """
    Background task to run the grading pipeline for specific students only.
    This function processes only the specified student submissions, not all submissions.
    """
    print(f"SPECIFIC GRADING TASK: Starting grading process for {len(student_ids)} students in coursework {coursework_id}")
    
    # Create a new database session
    db = db_session_maker()
    
    try:
        # Update task status in database
        grading_task = db.query(GradingTask).filter(GradingTask.task_id == task_id).first()
        if grading_task:
            grading_task.status = "RUNNING"
            grading_task.message = f"Grading {len(student_ids)} specific submissions..."
            grading_task.progress = 0
            db.commit()
    
        exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        
        # Check if required files exist
        answer_key_json = exam_folder_path / "answer_key.json"
        student_ocr_dir = exam_folder_path / "student_submissions_ocr"
        
        if not answer_key_json.exists():
            raise RuntimeError("Answer key JSON not found. OCR processing may have failed.")
        
        if not student_ocr_dir.exists():
            raise RuntimeError("Student OCR directory not found.")
        
        # Check if the specific student OCR files exist
        student_ocr_files = []
        for student_id in student_ids:
            student_ocr_file = student_ocr_dir / f"{student_id}.json"
            if student_ocr_file.exists():
                student_ocr_files.append(student_ocr_file)
            else:
                print(f"SPECIFIC GRADING TASK: OCR file not found for student {student_id}")
        
        if not student_ocr_files:
            raise RuntimeError("No OCR files found for specified students.")
        
        print(f"SPECIFIC GRADING TASK: Found {len(student_ocr_files)} OCR files to process")
        
        # Update progress
        if grading_task:
            grading_task.message = f"Processing {len(student_ocr_files)} submissions..."
            grading_task.progress = 10
            db.commit()
        
        # Run grading pipeline for specific students only
        from grading_wrapper import run_grading_pipeline
        
        # Create a temporary directory structure for specific students
        temp_dir = exam_folder_path / "temp_grading" / task_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_student_ocr_dir = temp_dir / "student_submissions_ocr"
        temp_student_ocr_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy only the specific student OCR files to temp directory
        for student_ocr_file in student_ocr_files:
            shutil.copy2(student_ocr_file, temp_student_ocr_dir / student_ocr_file.name)
        
        # Copy answer key to temp directory
        temp_answer_key = temp_dir / "answer_key.json"
        shutil.copy2(answer_key_json, temp_answer_key)
        
        # Update progress
        if grading_task:
            grading_task.message = "Running grading pipeline..."
            grading_task.progress = 30
            db.commit()
        
        # Run grading pipeline on temp directory
        try:
            run_grading_pipeline(str(temp_dir), grading_version)
            print(f"SPECIFIC GRADING TASK: Grading pipeline completed successfully")
        except Exception as e:
            print(f"SPECIFIC GRADING TASK ERROR: Grading pipeline failed. Error: {e}")
            raise
        
        # Update progress
        if grading_task:
            grading_task.message = "Updating database with results..."
            grading_task.progress = 80
            db.commit()
        
        # Process results and update database
        # Check if prodigy data files were created (actual output of grading pipeline)
        prodigy_data_dir = temp_dir / "prodigy_data"
        if prodigy_data_dir.exists():
            # Copy results back to main server directory
            main_prodigy_dir = exam_folder_path / "prodigy_data"
            main_prodigy_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy all result files to main directory
            for result_file in prodigy_data_dir.glob("*.jsonl"):
                dest_file = main_prodigy_dir / result_file.name
                shutil.copy2(result_file, dest_file)
                print(f"SPECIFIC GRADING TASK: Copied {result_file.name} to main directory")
            
            # Look for student-specific result files and update database
            for student_id in student_ids:
                student_result_file = prodigy_data_dir / f"{student_id}_prodigy.jsonl"
                if student_result_file.exists() and student_result_file.stat().st_size > 0:
                    # File exists and has content, update status to GRADED
                    submission = db.query(SubmissionRecord).filter(
                        SubmissionRecord.coursework_id == coursework_id,
                        SubmissionRecord.student_id == student_id
                    ).first()
                    
                    if submission:
                        submission.status = "GRADED"
                        print(f"SPECIFIC GRADING TASK: Updated student {student_id} to GRADED status")
                    else:
                        print(f"SPECIFIC GRADING TASK: No database record found for student {student_id}")
                else:
                    # Mark as grading failed if no result file
                    submission = db.query(SubmissionRecord).filter(
                        SubmissionRecord.coursework_id == coursework_id,
                        SubmissionRecord.student_id == student_id
                    ).first()
                    
                    if submission:
                        submission.status = "GRADING_FAILED"
                        print(f"SPECIFIC GRADING TASK: Marked student {student_id} as GRADING_FAILED")
            
            db.commit()
        else:
            print("SPECIFIC GRADING TASK: No prodigy_data directory found in temp results")
            # Mark all students as grading failed
            for student_id in student_ids:
                submission = db.query(SubmissionRecord).filter(
                    SubmissionRecord.coursework_id == coursework_id,
                    SubmissionRecord.student_id == student_id
                ).first()
                
                if submission:
                    submission.status = "GRADING_FAILED"
                    print(f"SPECIFIC GRADING TASK: Marked student {student_id} as GRADING_FAILED (no results)")
            
            db.commit()
        
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Update final task status
        if grading_task:
            grading_task.status = "COMPLETED"
            grading_task.message = f"Successfully graded {len(student_ids)} submissions"
            grading_task.progress = 100
            db.commit()
        
        print(f"SPECIFIC GRADING TASK: Completed successfully for {len(student_ids)} students")
        
    except Exception as e:
        print(f"SPECIFIC GRADING TASK FAILED: {e}")
        import traceback
        traceback.print_exc()
        
        # Update task status to failed
        if grading_task:
            grading_task.status = "FAILED"
            grading_task.message = f"Grading failed: {str(e)}"
            db.commit()
    finally:
        if db:
            db.close()
            print(f"SPECIFIC GRADING TASK: Database connection closed")
