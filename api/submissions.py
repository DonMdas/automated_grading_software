"""
Submissions API endpoints for the AI Studio application.
"""

import io
import json
import shutil
import threading
import uuid
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, get_mongo_db, Submission, Student, Assignment, Course, Exam, SessionLocal
from auth import get_current_user
from services.google_services import get_classroom_service
from config import SERVER_DATA_DIR

router = APIRouter()

@router.get("/api/submissions/status/{coursework_id}")
async def get_submissions_status(
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get the status of all submissions for a coursework."""
    # Find the assignment by Google ID
    assignment = db.query(Assignment).filter(
        Assignment.google_assignment_id == coursework_id
    ).first()
    
    if not assignment:
        return {
            "coursework_id": coursework_id,
            "total_submissions": 0,
            "submissions": [],
            "summary": {
                "downloaded": 0,
                "ocr_complete": 0,
                "ocr_failed": 0,
                "graded": 0,
                "grading_failed": 0
            }
        }
    
    submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment.id
    ).all()
    
    if not submissions:
        return {
            "coursework_id": coursework_id,
            "total_submissions": 0,
            "submissions": [],
            "summary": {
                "downloaded": 0,
                "ocr_complete": 0,
                "ocr_failed": 0,
                "graded": 0,
                "grading_failed": 0
            }
        }
    
    # Count submissions by status
    status_count = {}
    submission_list = []
    
    for submission in submissions:
        status = submission.status
        status_count[status] = status_count.get(status, 0) + 1
        
        # Check if result file exists for graded submissions
        result_file_exists = False
        if status == "GRADED":
            exam_folder_path = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
            student_result_file = exam_folder_path / "prodigy_data" / f"{submission.student.google_student_id}_prodigy.jsonl"
            result_file_exists = student_result_file.exists()
            
            # DON'T modify the database here - this is a read operation
            # The database should only be updated by the grading processes
            # If the file doesn't exist, it might be temporarily moved or there's a timing issue
            # Let the grading processes handle status updates
        
        submission_list.append({
            "student_id": submission.student.google_student_id,
            "student_name": submission.student.name,
            "status": status,
            "created_at": submission.created_at,
            "result_file_exists": result_file_exists,
            "can_view_results": status == "GRADED" and result_file_exists,
            "google_submission_id": submission.google_submission_id,
            "is_ready_for_processing": status in ["PENDING", "DOWNLOADED", "OCR_COMPLETE", "GRADED"]
        })
    
    return {
        "coursework_id": coursework_id,
        "total_submissions": len(submissions),
        "submissions": submission_list,
        "summary": {
            "pending": status_count.get("PENDING", 0),
            "downloaded": status_count.get("DOWNLOADED", 0),
            "ocr_complete": status_count.get("OCR_COMPLETE", 0),
            "ocr_failed": status_count.get("OCR_FAILED", 0),
            "graded": status_count.get("GRADED", 0),
            "grading_failed": status_count.get("GRADING_FAILED", 0),
            "not_submitted": sum(1 for s in status_count.keys() if s.startswith("NOT_SUBMITTED_")),
            "ready_for_processing": sum(1 for s in status_count.keys() if s in ["PENDING", "DOWNLOADED", "OCR_COMPLETE", "GRADED"])
        }
    }

@router.post("/api/submissions/load/{course_id}/{coursework_id}")
async def load_submissions_from_classroom(
    course_id: str,
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    service=Depends(get_classroom_service)
):
    """
    Load submissions from Google Classroom and store basic info in database.
    This allows viewing submissions without requiring evaluation first.
    """
    try:
        # Get or create course
        course = db.query(Course).filter(Course.google_course_id == course_id).first()
        if not course:
            # Get course info from Google Classroom
            course_info = service.courses().get(id=course_id).execute()
            course = Course(
                google_course_id=course_id,
                name=course_info.get('name', f'Course {course_id}'),
                description=course_info.get('description', ''),
                teacher_id=current_user.id
            )
            db.add(course)
            db.commit()
        
        # Get or create assignment
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        if not assignment:
            # Get assignment info from Google Classroom
            assignment_info = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
            assignment = Assignment(
                google_assignment_id=coursework_id,
                course_id=course.id,
                title=assignment_info.get('title', f'Assignment {coursework_id}'),
                description=assignment_info.get('description', '')
            )
            db.add(assignment)
            db.commit()
        
        # Create or get exam for this assignment
        exam = db.query(Exam).filter(Exam.assignment_id == assignment.id).first()
        if not exam:
            exam = Exam(
                assignment_id=assignment.id,
                title=f"Exam for {assignment.title}",
                status="ACTIVE"
            )
            db.add(exam)
            db.commit()
        
        # Get submissions from Google Classroom
        submission_results = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, 
            courseWorkId=coursework_id
        ).execute()
        submissions = submission_results.get('studentSubmissions', [])
        
        if not submissions:
            return {
                "message": "No submissions found in Google Classroom",
                "loaded_count": 0,
                "total_count": 0
            }
        
        # Create coursework directory
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        assignment_dir.mkdir(parents=True, exist_ok=True)
        
        loaded_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        for sub in submissions:
            student_id = sub.get('userId')
            submission_state = sub.get('state')
            submission_id = sub.get('id')
            
            print(f"LOAD DEBUG: Processing submission {submission_id} for student {student_id} - state: {submission_state}")
            
            # Skip if no student ID
            if not student_id:
                skipped_count += 1
                errors.append(f"Skipped submission {submission_id}: No student ID")
                print(f"LOAD DEBUG: Skipped - no student ID")
                continue
            
            # Check if submission already exists in database
            existing_submission = db.query(Submission).filter(
                Submission.google_submission_id == submission_id
            ).first()
            
            if existing_submission:
                skipped_count += 1
                print(f"LOAD DEBUG: Skipped - already exists in database")
                continue  # Skip if already exists
            
            try:
                # Get student profile
                print(f"LOAD DEBUG: Getting student profile for {student_id}")
                try:
                    student_profile = service.userProfiles().get(userId=student_id).execute()
                    student_name = student_profile.get('name', {}).get('fullName', 'Unknown Student')
                    print(f"LOAD DEBUG: Student name: {student_name}")
                except Exception as profile_error:
                    student_name = f"Student_{student_id}"
                    print(f"LOAD DEBUG: Failed to get student profile: {profile_error}, using default name")
                
                # Create student record if not exists - enhanced for multiple courses
                print(f"LOAD DEBUG: Creating/getting student record for any classroom")
                
                # With the new schema, we can directly look for student in this course
                db_student = db.query(Student).filter(
                    Student.google_student_id == student_id,
                    Student.course_id == course.id
                ).first()
                
                if not db_student:
                    # Student doesn't exist in this course, create new record
                    print(f"LOAD DEBUG: Creating new student record")
                    try:
                        db_student = Student(
                            google_student_id=student_id, 
                            name=student_name,
                            course_id=course.id
                        )
                        db.add(db_student)
                        db.commit()
                        print(f"LOAD DEBUG: Student record created with ID: {db_student.id}")
                    except Exception as create_error:
                        print(f"LOAD DEBUG: Student creation failed: {create_error}")
                        db.rollback()
                        
                        # Try to find the student again in case it was created by another process
                        db_student = db.query(Student).filter(
                            Student.google_student_id == student_id,
                            Student.course_id == course.id
                        ).first()
                        
                        if not db_student:
                            print(f"LOAD DEBUG: Final attempt to create student with fallback strategy")
                            # Final fallback - this should not happen with the new schema
                            raise Exception(f"Failed to create student record: {create_error}")
                        else:
                            print(f"LOAD DEBUG: Found student after failed creation: {db_student.id}")
                else:
                    print(f"LOAD DEBUG: Student record found with ID: {db_student.id}")
                    # Update student name if it has changed
                    if db_student.name != student_name:
                        try:
                            db_student.name = student_name
                            db.commit()
                            print(f"LOAD DEBUG: Updated student name to: {student_name}")
                        except:
                            db.rollback()
                            print(f"LOAD DEBUG: Failed to update student name, continuing...")
                
                # Get attachment info if available
                print(f"LOAD DEBUG: Processing attachments")
                attachments = sub.get('assignmentSubmission', {}).get('attachments', [])
                file_id = None
                for attachment in attachments:
                    if 'driveFile' in attachment:
                        file_id = attachment['driveFile'].get('id')
                        break
                print(f"LOAD DEBUG: Found file ID: {file_id}")
                
                # Determine initial status based on submission state
                if submission_state == 'TURNED_IN':
                    initial_status = "PENDING"  # Ready to be processed
                else:
                    initial_status = f"NOT_SUBMITTED_{submission_state}"  # Not ready for processing
                
                print(f"LOAD DEBUG: Setting initial status: {initial_status}")
                
                # Create submission record
                print(f"LOAD DEBUG: Creating submission record")
                submission_record = Submission(
                    google_submission_id=submission_id,
                    exam_id=exam.id,
                    assignment_id=assignment.id,
                    student_id=db_student.id,
                    google_drive_id=file_id,
                    local_file_path=None,  # Will be set when files are downloaded
                    status=initial_status
                )
                db.add(submission_record)
                db.commit()
                print(f"LOAD DEBUG: Submission record created with ID: {submission_record.id}")
                loaded_count += 1
                
            except Exception as e:
                error_count += 1
                error_msg = f"Failed to process submission {submission_id} for student {student_id}: {str(e)}"
                errors.append(error_msg)
                print(f"LOAD DEBUG ERROR: {error_msg}")
                
                # Rollback the transaction for this submission to continue with others
                try:
                    db.rollback()
                    print(f"LOAD DEBUG: Rolled back transaction for submission {submission_id}")
                except Exception as rollback_error:
                    print(f"LOAD DEBUG: Rollback failed: {rollback_error}")
                
                import traceback
                traceback.print_exc()
                continue
        
        db.commit()
        
        result = {
            "message": f"Loaded {loaded_count} submissions from Google Classroom ({skipped_count} skipped, {error_count} errors)",
            "loaded_count": loaded_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "total_count": len(submissions),
            "coursework_id": coursework_id
        }
        
        if errors:
            result["errors"] = errors
        
        # If we loaded any submissions, trigger OCR processing for them
        if loaded_count > 0:
            print(f"LOAD DEBUG: Triggering OCR processing for {loaded_count} newly loaded submissions")
            try:
                # Process OCR for newly loaded submissions
                await process_ocr_for_new_submissions(
                    course_id=course_id,
                    coursework_id=coursework_id,
                    db=db,
                    service=service
                )
                result["ocr_processing"] = "triggered"
            except Exception as ocr_error:
                print(f"LOAD DEBUG: Failed to trigger OCR processing: {ocr_error}")
                result["ocr_processing"] = f"failed: {str(ocr_error)}"
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load submissions from Google Classroom: {str(e)}"
        )

@router.get("/api/submissions/summary/{course_id}/{coursework_id}")
async def get_submission_summary(
    course_id: str, 
    coursework_id: str, 
    service=Depends(get_classroom_service)
):
    """Get a summary of submissions including how many students are expected vs submitted."""
    try:
        # Get all students in the course
        students_response = service.courses().students().list(courseId=course_id).execute()
        total_students = len(students_response.get('students', []))
        
        # Get submissions for this coursework
        submissions_response = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, 
            courseWorkId=coursework_id
        ).execute()
        submissions = submissions_response.get('studentSubmissions', [])
        
        # Count different submission states
        turned_in = sum(1 for sub in submissions if sub.get('state') == 'TURNED_IN')
        created = sum(1 for sub in submissions if sub.get('state') == 'CREATED')
        returned = sum(1 for sub in submissions if sub.get('state') == 'RETURNED')
        
        return {
            "total_students": total_students,
            "total_submissions": len(submissions),
            "turned_in": turned_in,
            "created": created,  # Students who have the assignment but haven't submitted
            "returned": returned,  # Graded submissions
            "not_started": total_students - len(submissions),  # Students who don't even have the assignment yet
            "completion_rate": round((turned_in / total_students * 100), 1) if total_students > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get submission summary: {e}")

@router.post("/api/submissions/evaluate-new/{course_id}/{coursework_id}")
async def evaluate_new_submissions(
    course_id: str,
    coursework_id: str,
    background_tasks: BackgroundTasks,
    answer_key: UploadFile = File(None),
    grading_version: str = Form("v2"),  # Accept grading version from form data
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    service=Depends(get_classroom_service)
):
    """
    Evaluate only new/ungraded submissions for a coursework.
    If answer_key.json already exists, it will be reused without requiring a new PDF.
    """
    from background_tasks import process_specific_submissions
    
    print(f"API: Starting evaluation for new submissions in coursework {coursework_id} with grading version {grading_version}")
    
    # Validate grading version
    if grading_version not in ["v1", "v2"]:
        grading_version = "v2"  # Default to v2 if invalid
        print(f"API: Invalid grading version provided, defaulting to v2")
    
    # Check for ungraded submissions
    assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
    if not assignment:
        return {
            "message": "Assignment not found",
            "count": 0
        }
    
    ungraded_submissions = db.query(Submission).filter(
        Submission.assignment_id == assignment.id,
        Submission.status.in_(["PENDING", "DOWNLOADED", "OCR_COMPLETE", "GRADING_FAILED"])
    ).all()
    
    if not ungraded_submissions:
        return {
            "message": "No new submissions to evaluate",
            "count": 0
        }
    
    # Check if answer key directory exists
    assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
    assignment_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if answer_key.json already exists
    answer_key_json_path = assignment_dir / "answer_key.json"
    answer_key_pdf_path = assignment_dir / "answer_key.pdf"
    
    if answer_key_json_path.exists():
        # Use existing answer key JSON - no need for new PDF
        answer_key_path = str(answer_key_json_path)
        print(f"Using existing answer key JSON: {answer_key_path}")
    else:
        # Require new answer key PDF
        if not answer_key:
            raise HTTPException(
                status_code=400,
                detail="Answer key PDF is required as no existing answer key was found"
            )
        
        # Save the new answer key PDF
        with open(answer_key_pdf_path, "wb") as buffer:
            shutil.copyfileobj(answer_key.file, buffer)
        answer_key_path = str(answer_key_pdf_path)
        print(f"Saved new answer key PDF: {answer_key_path}")
    
    # Get submission IDs to process
    submission_ids = [sub.student.google_student_id for sub in ungraded_submissions]
    
    # Start background task for specific submissions using threading
    processing_thread = threading.Thread(
        target=process_specific_submissions,
        args=(course_id, coursework_id, answer_key_path, service, SessionLocal, submission_ids, grading_version, str(current_user.id))
    )
    processing_thread.start()
    
    return {
        "message": f"Started evaluation for {len(ungraded_submissions)} new submissions using grading version {grading_version}",
        "count": len(ungraded_submissions),
        "grading_version": grading_version,
        "submission_ids": submission_ids,
        "used_existing_answer_key": answer_key_json_path.exists()
    }

@router.post("/api/submissions/evaluate-single/{course_id}/{coursework_id}/{student_id}")
async def evaluate_single_submission(
    course_id: str,
    coursework_id: str,
    student_id: str,
    background_tasks: BackgroundTasks,
    answer_key: UploadFile = File(None),
    grading_version: str = Form("v2"),  # Default to v2, accept from form data
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    service=Depends(get_classroom_service)
):
    """
    Evaluate a single submission. Useful for late submissions or re-grading.
    If answer_key.json already exists, it will be reused without requiring a new PDF.
    """
    try:
        from background_tasks import process_specific_submissions
        
        print(f"API: Starting evaluation for student {student_id} in coursework {coursework_id} with grading version {grading_version}")
        
        # Validate grading version
        if grading_version not in ["v1", "v2"]:
            grading_version = "v2"  # Default to v2 if invalid
            print(f"API: Invalid grading version provided, defaulting to v2")
        
        # Check if submission exists
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        if not assignment:
            raise HTTPException(
                status_code=404,
                detail=f"Assignment {coursework_id} not found"
            )
        
        submission = db.query(Submission).join(Student).filter(
            Submission.assignment_id == assignment.id,
            Student.google_student_id == student_id
        ).first()
        
        if not submission:
            print(f"API ERROR: No submission found for student {student_id} in coursework {coursework_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No submission found for student {student_id} in coursework {coursework_id}"
            )
        
        # Check if answer key directory exists
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        assignment_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if answer_key.json already exists
        answer_key_json_path = assignment_dir / "answer_key.json"
        answer_key_pdf_path = assignment_dir / "answer_key.pdf"
        
        if answer_key_json_path.exists():
            # Use existing answer key JSON - no need for new PDF
            answer_key_path = str(answer_key_json_path)
            print(f"API: Using existing answer key JSON: {answer_key_path}")
            used_existing_answer_key = True
        else:
            # Require new answer key PDF
            if not answer_key:
                print(f"API ERROR: Answer key PDF is required as no existing answer key was found")
                raise HTTPException(
                    status_code=400,
                    detail="Answer key PDF is required as no existing answer key was found"
                )
            
            # Save the new answer key PDF
            with open(answer_key_pdf_path, "wb") as buffer:
                shutil.copyfileobj(answer_key.file, buffer)
            answer_key_path = str(answer_key_pdf_path)
            print(f"API: Saved new answer key PDF: {answer_key_path}")
            used_existing_answer_key = False
        
        # Start background task for single submission
        print(f"API: Starting background task for student {student_id} with grading version {grading_version}")
        
        # Use threading to avoid blocking the main application
        import threading
        processing_thread = threading.Thread(
            target=process_specific_submissions,
            args=(course_id, coursework_id, answer_key_path, service, SessionLocal, [student_id], grading_version, str(current_user.id))
        )
        processing_thread.start()
        
        print(f"API: Successfully started evaluation thread for student {submission.student.name}")
        return {
            "message": f"Started evaluation for student {submission.student.name} using grading version {grading_version}",
            "student_id": student_id,
            "student_name": submission.student.name,
            "grading_version": grading_version,
            "used_existing_answer_key": used_existing_answer_key
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"API ERROR: Unexpected error in evaluate_single_submission: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/api/submissions/test")
async def test_endpoint():
    """Test endpoint to verify the submissions API is working."""
    return {"message": "Submissions API is working", "timestamp": datetime.now().isoformat()}

@router.get("/api/submissions/debug/{coursework_id}")
async def debug_submissions(
    coursework_id: str,
    current_user = Depends(get_current_user)
):
    """Debug endpoint to check submissions loading"""
    from database import SessionLocal, Assignment, Course, Submission
    
    db = SessionLocal()
    try:
        # Check if assignment exists
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        assignment_info = None
        if assignment:
            assignment_info = {
                "id": str(assignment.id),
                "title": assignment.title,
                "google_assignment_id": assignment.google_assignment_id,
                "course_id": str(assignment.course_id)
            }
        
        # Check submissions
        submissions = []
        if assignment:
            submissions = db.query(Submission).filter(
                Submission.assignment_id == assignment.id
            ).all()
            submissions = [{"id": str(s.id), "status": s.status, "google_submission_id": s.google_submission_id} for s in submissions]
        
        return {
            "coursework_id": coursework_id,
            "assignment_found": assignment is not None,
            "assignment_info": assignment_info,
            "submissions_count": len(submissions),
            "submissions": submissions
        }
    finally:
        db.close()

@router.get("/api/submissions/debug-classroom/{course_id}/{coursework_id}")
async def debug_classroom_submissions(
    course_id: str,
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    service=Depends(get_classroom_service)
):
    """
    Debug endpoint to check submissions directly from Google Classroom.
    This helps troubleshoot why submissions might not be loading.
    """
    try:
        # Get submissions from Google Classroom
        submission_results = service.courses().courseWork().studentSubmissions().list(
            courseId=course_id, 
            courseWorkId=coursework_id
        ).execute()
        submissions = submission_results.get('studentSubmissions', [])
        
        debug_info = {
            "total_submissions": len(submissions),
            "submissions": []
        };
        
        for sub in submissions:
            student_id = sub.get('userId')
            submission_state = sub.get('state')
            submission_id = sub.get('id')
            
            # Get student profile
            try:
                student_profile = service.userProfiles().get(userId=student_id).execute()
                student_name = student_profile.get('name', {}).get('fullName', 'Unknown Student')
            except:
                student_name = f"Student_{student_id}"
            
            # Check if submission exists in database
            existing_submission = db.query(Submission).filter(
                Submission.google_submission_id == submission_id
            ).first()
            
            # Get attachment info
            attachments = sub.get('assignmentSubmission', {}).get('attachments', [])
            has_attachments = len(attachments) > 0
            
            submission_info = {
                "submission_id": submission_id,
                "student_id": student_id,
                "student_name": student_name,
                "state": submission_state,
                "has_attachments": has_attachments,
                "attachments_count": len(attachments),
                "exists_in_db": existing_submission is not None,
                "db_status": existing_submission.status if existing_submission else None,
                "created_at": sub.get('creationTime'),
                "updated_at": sub.get('updateTime')
            }
            
            debug_info["submissions"].append(submission_info)
        
        # Also get database submissions for comparison
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        db_submissions = []
        if assignment:
            db_subs = db.query(Submission).filter(
                Submission.assignment_id == assignment.id
            ).all()
            
            for db_sub in db_subs:
                db_submissions.append({
                    "submission_id": db_sub.google_submission_id,
                    "student_id": db_sub.student.google_student_id if db_sub.student else None,
                    "student_name": db_sub.student.name if db_sub.student else None,
                    "status": db_sub.status,
                    "created_at": db_sub.created_at,
                    "local_file_path": db_sub.local_file_path
                })
        
        debug_info["database_submissions"] = db_submissions
        debug_info["database_submissions_count"] = len(db_submissions)
        
        return debug_info
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to debug submissions: {str(e)}"
        )

@router.get("/api/submissions/investigate/{assignment_title}")
async def investigate_assignment_by_title(
    assignment_title: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Investigate an assignment by its title to help debug submission issues.
    """
    try:
        # Search for assignments with the given title (case-insensitive)
        assignments = db.query(Assignment).filter(Assignment.title.ilike(f'%{assignment_title}%')).all()
        
        result = {
            "search_term": assignment_title,
            "assignments_found": len(assignments),
            "assignments": []
        }
        
        if not assignments:
            # Also return all assignments for reference
            all_assignments = db.query(Assignment).all()
            result["message"] = f"No assignments found with '{assignment_title}' in title"
            result["all_assignments"] = [
                {
                    "google_assignment_id": a.google_assignment_id,
                    "title": a.title,
                    "created_at": a.created_at
                } for a in all_assignments
            ]
        else:
            for assignment in assignments:
                # Get course details
                course = db.query(Course).filter(Course.id == assignment.course_id).first()
                
                # Get exam details
                exam = db.query(Exam).filter(Exam.assignment_id == assignment.id).first()
                
                # Get submissions
                submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
                
                submission_details = []
                for sub in submissions:
                    student = db.query(Student).filter(Student.id == sub.student_id).first()
                    submission_details.append({
                        "student_name": student.name if student else "Unknown",
                        "student_google_id": student.google_student_id if student else "Unknown",
                        "status": sub.status,
                        "google_submission_id": sub.google_submission_id,
                        "local_file_path": sub.local_file_path,
                        "google_drive_id": sub.google_drive_id,
                        "created_at": sub.created_at
                    })
                
                # Check file system
                from pathlib import Path
                server_data_dir = Path(f"{SERVER_DATA_DIR}/{assignment.google_assignment_id}")
                file_system_info = {
                    "directory_exists": server_data_dir.exists(),
                    "directory_path": str(server_data_dir),
                    "contents": []
                }
                
                if server_data_dir.exists():
                    for item in server_data_dir.iterdir():
                        if item.is_file():
                            file_system_info["contents"].append({
                                "type": "file",
                                "name": item.name,
                                "size": item.stat().st_size
                            })
                        elif item.is_dir():
                            sub_contents = list(item.iterdir())
                            file_system_info["contents"].append({
                                "type": "directory",
                                "name": item.name,
                                "items_count": len(sub_contents),
                                "items": [sub_item.name for sub_item in sub_contents]
                            })
                
                assignment_info = {
                    "google_assignment_id": assignment.google_assignment_id,
                    "title": assignment.title,
                    "database_id": str(assignment.id),
                    "course_id": str(assignment.course_id),
                    "created_at": assignment.created_at,
                    "course": {
                        "name": course.name if course else "Unknown",
                        "google_course_id": course.google_course_id if course else "Unknown"
                    } if course else None,
                    "exam": {
                        "title": exam.title if exam else "No exam",
                        "id": str(exam.id) if exam else None
                    } if exam else None,
                    "submissions_count": len(submissions),
                    "submissions": submission_details,
                    "file_system": file_system_info,
                    "debug_urls": {
                        "google_classroom_debug": f"/api/submissions/debug-classroom/{course.google_course_id if course else 'UNKNOWN'}/{assignment.google_assignment_id}",
                        "database_debug": f"/api/submissions/debug/{assignment.google_assignment_id}"
                    }
                }
                
                result["assignments"].append(assignment_info)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to investigate assignment: {str(e)}"
        )

async def process_ocr_for_new_submissions(course_id: str, coursework_id: str, db: Session, service):
    """
    Process OCR for newly loaded submissions that are in PENDING status.
    This function downloads the PDF files and extracts text using OCR.
    Works with any Google account and classroom.
    """
    print(f"OCR PROCESSING: Starting OCR for new submissions in coursework {coursework_id}")
    
    try:
        # Get assignment
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        if not assignment:
            print(f"OCR PROCESSING ERROR: Assignment not found for coursework {coursework_id}")
            return
        
        # Get submissions that need OCR processing
        pending_submissions = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.status == "PENDING"
        ).all()
        
        print(f"OCR PROCESSING: Found {len(pending_submissions)} submissions needing OCR")
        
        if not pending_submissions:
            print("OCR PROCESSING: No submissions need OCR processing")
            return
        
        # Create directories
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        assignment_dir.mkdir(parents=True, exist_ok=True)
        submissions_dir = assignment_dir / "submissions"
        submissions_dir.mkdir(exist_ok=True)
        student_ocr_dir = assignment_dir / "student_submissions_ocr"
        student_ocr_dir.mkdir(exist_ok=True)
        
        # Setup Google Drive service using the same credentials as the classroom service
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        
        try:
            # Extract credentials from the classroom service
            credentials = service._http.credentials
            drive_service = build('drive', 'v3', credentials=credentials)
            print("OCR PROCESSING: Drive service initialized successfully")
        except Exception as e:
            print(f"OCR PROCESSING ERROR: Failed to initialize Drive service: {e}")
            # Try alternative approach
            try:
                from services.google_services import get_drive_service
                from auth import get_current_user
                # This won't work in async context, so we'll use a different approach
                drive_service = build('drive', 'v3', credentials=credentials)
                print("OCR PROCESSING: Drive service initialized via fallback")
            except Exception as fallback_e:
                print(f"OCR PROCESSING ERROR: Fallback also failed: {fallback_e}")
                return
        
        # Import OCR function
        from ocr_code.studentanswer import extract_student_answers_to_json
        
        processed_count = 0
        failed_count = 0
        
        # Process each submission
        for submission in pending_submissions:
            student = submission.student
            if not student:
                print(f"OCR PROCESSING: Skipping submission {submission.id} - no student found")
                continue
            
            student_id = student.google_student_id
            print(f"OCR PROCESSING: Processing submission for student {student_id}")
            
            try:
                # Get the Google Classroom submission to get drive file info
                classroom_submission = None
                try:
                    classroom_submission = service.courses().courseWork().studentSubmissions().get(
                        courseId=course_id,
                        courseWorkId=coursework_id,
                        id=submission.google_submission_id
                    ).execute()
                except Exception as e:
                    print(f"OCR PROCESSING ERROR: Failed to get classroom submission for {student_id}: {e}")
                    continue
                
                if not classroom_submission:
                    print(f"OCR PROCESSING: No classroom submission found for student {student_id}")
                    continue
                
                # Get the drive file info
                attachment = classroom_submission.get('assignmentSubmission', {}).get('attachments', [])
                if not attachment:
                    print(f"OCR PROCESSING: No attachments found for student {student_id}")
                    submission.status = "NO_ATTACHMENTS"
                    continue
                
                drive_file = attachment[0].get('driveFile')
                if not drive_file:
                    print(f"OCR PROCESSING: No drive file found for student {student_id}")
                    submission.status = "NO_DRIVE_FILE"
                    continue
                
                file_id = drive_file.get('id')
                original_name = drive_file.get('title', f"file_{file_id}")
                file_extension = Path(original_name).suffix or '.pdf'
                local_path = submissions_dir / f"{student_id}{file_extension}"
                
                # Download the file if not already downloaded
                if not local_path.exists():
                    print(f"OCR PROCESSING: Downloading file for student {student_id}...")
                    try:
                        request = drive_service.files().get_media(fileId=file_id)
                        with io.FileIO(local_path, 'wb') as f:
                            downloader = MediaIoBaseDownload(f, request)
                            done = False
                            while not done:
                                _, done = downloader.next_chunk()
                        print(f"OCR PROCESSING: Download complete for student {student_id}")
                    except Exception as download_e:
                        print(f"OCR PROCESSING ERROR: Failed to download file for student {student_id}: {download_e}")
                        submission.status = "DOWNLOAD_FAILED"
                        continue
                else:
                    print(f"OCR PROCESSING: File already exists for student {student_id}")
                
                # Update local file path
                submission.local_file_path = str(local_path)
                submission.status = "DOWNLOADED"
                
                # Process OCR if it's a PDF
                if local_path.suffix.lower() == '.pdf':
                    print(f"OCR PROCESSING: Extracting text from PDF for student {student_id}")
                    student_ocr_path = student_ocr_dir / f"{student_id}.json"
                    
                    try:
                        extract_student_answers_to_json(str(local_path), str(student_ocr_path))
                        print(f"OCR PROCESSING: OCR complete for student {student_id}")
                        
                        # Store in MongoDB if available (optional - don't fail if MongoDB isn't available)
                        try:
                            from db_service import get_db_service
                            db_service = get_db_service(db)
                            with open(student_ocr_path, 'r') as f:
                                student_answers = json.load(f)
                            
                            mongo_id = db_service.store_student_answers(str(submission.id), student_answers)
                            print(f"OCR PROCESSING: Student answers stored in MongoDB with ID: {mongo_id}")
                        except Exception as mongo_e:
                            print(f"OCR PROCESSING WARNING: Failed to store in MongoDB: {mongo_e}")
                            print("OCR PROCESSING: Continuing without MongoDB storage...")
                        
                        submission.status = "OCR_COMPLETE"
                        processed_count += 1
                        
                    except Exception as ocr_e:
                        print(f"OCR PROCESSING ERROR: OCR failed for student {student_id}: {ocr_e}")
                        submission.status = "OCR_FAILED"
                        failed_count += 1
                else:
                    print(f"OCR PROCESSING: Skipping OCR for non-PDF file: {local_path}")
                    submission.status = "DOWNLOADED_NON_PDF"
                    failed_count += 1
                
                db.commit()
                
            except Exception as e:
                print(f"OCR PROCESSING ERROR: Failed to process submission for student {student_id}: {e}")
                import traceback
                traceback.print_exc()
                submission.status = "PROCESSING_FAILED"
                failed_count += 1
                try:
                    db.commit()
                except:
                    db.rollback()
                continue
        
        print(f"OCR PROCESSING: Completed - {processed_count} processed, {failed_count} failed")
        
    except Exception as e:
        print(f"OCR PROCESSING ERROR: {e}")
        import traceback
        traceback.print_exc()

@router.post("/api/submissions/trigger-ocr/{course_id}/{coursework_id}")
async def trigger_ocr_processing(
    course_id: str,
    coursework_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    service=Depends(get_classroom_service)
):
    """
    Manually trigger OCR processing for submissions that are loaded but not yet processed.
    Useful for any Google account and classroom.
    """
    try:
        print(f"TRIGGER OCR: Starting OCR processing for coursework {coursework_id}")
        
        # Get assignment
        assignment = db.query(Assignment).filter(
            Assignment.google_assignment_id == coursework_id
        ).first()
        
        if not assignment:
            raise HTTPException(
                status_code=404,
                detail=f"Assignment not found for coursework {coursework_id}"
            )
        
        # Get submissions that need OCR processing
        pending_submissions = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.status.in_(["PENDING", "DOWNLOADED"])
        ).all()
        
        if not pending_submissions:
            return {
                "message": "No submissions need OCR processing",
                "processed_count": 0,
                "total_count": 0
            }
        
        # Process OCR for pending submissions
        await process_ocr_for_new_submissions(
            course_id=course_id,
            coursework_id=coursework_id,
            db=db,
            service=service
        )
        
        # Check results
        updated_submissions = db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.status.in_(["OCR_COMPLETE", "OCR_FAILED"])
        ).all()
        
        ocr_complete = len([s for s in updated_submissions if s.status == "OCR_COMPLETE"])
        ocr_failed = len([s for s in updated_submissions if s.status == "OCR_FAILED"])
        
        return {
            "message": f"OCR processing completed for {len(pending_submissions)} submissions",
            "processed_count": len(pending_submissions),
            "ocr_complete": ocr_complete,
            "ocr_failed": ocr_failed,
            "total_count": len(pending_submissions)
        }
        
    except Exception as e:
        print(f"TRIGGER OCR ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger OCR processing: {str(e)}"
        )

@router.get("/api/submissions/debug-ocr-files/{coursework_id}")
async def debug_ocr_files(
    coursework_id: str,
    current_user = Depends(get_current_user)
):
    """
    Debug endpoint to check what OCR files exist for a coursework.
    Helps troubleshoot OCR file location and naming issues.
    """
    try:
        assignment_dir = Path(f"{SERVER_DATA_DIR}/{coursework_id}")
        
        result = {
            "coursework_id": coursework_id,
            "assignment_directory": str(assignment_dir),
            "directory_exists": assignment_dir.exists(),
            "ocr_files": {
                "student_submissions_ocr": [],
                "legacy_student_answers": [],
                "other_json_files": []
            }
        }
        
        if assignment_dir.exists():
            # Check student_submissions_ocr directory
            student_ocr_dir = assignment_dir / "student_submissions_ocr"
            if student_ocr_dir.exists():
                for file in student_ocr_dir.glob("*.json"):
                    result["ocr_files"]["student_submissions_ocr"].append({
                        "filename": file.name,
                        "student_id": file.stem,
                        "size": file.stat().st_size,
                        "path": str(file)
                    })
            
            # Check for legacy naming pattern
            for file in assignment_dir.glob("student_answers_*.json"):
                student_id = file.name.replace("student_answers_", "").replace(".json", "")
                result["ocr_files"]["legacy_student_answers"].append({
                    "filename": file.name,
                    "student_id": student_id,
                    "size": file.stat().st_size,
                    "path": str(file),
                    "should_move_to": str(student_ocr_dir / f"{student_id}.json")
                })
            
            # Check for other JSON files
            for file in assignment_dir.glob("*.json"):
                if not file.name.startswith("student_answers_") and file.name != "answer_key.json":
                    result["ocr_files"]["other_json_files"].append({
                        "filename": file.name,
                        "size": file.stat().st_size,
                        "path": str(file)
                    })
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to debug OCR files: {str(e)}"
        )