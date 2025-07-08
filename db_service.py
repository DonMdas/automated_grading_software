"""
Database service layer for the AI Studio application.
This module provides high-level database operations for both PostgreSQL and MongoDB.
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from pathlib import Path

from database import (
    User, UserSession, Course, Assignment, Student, Exam, Submission, GradingTask,
    mongo_manager, get_db, SessionLocal
)
from config import SERVER_DATA_DIR

class DatabaseService:
    """High-level database service for the AI Studio application"""
    
    def __init__(self, db_session: Session = None):
        self.db = db_session or SessionLocal()
        self.mongo = mongo_manager
    
    def close(self):
        """Close the database session"""
        if self.db:
            self.db.close()
    
    # Course Operations
    def get_or_create_course(self, google_course_id: str, course_info: Dict, teacher_id: uuid.UUID) -> Course:
        """Get or create a course from Google Classroom data"""
        course = self.db.query(Course).filter(Course.google_course_id == google_course_id).first()
        if not course:
            course = Course(
                google_course_id=google_course_id,
                name=course_info.get('name', f'Course {google_course_id}'),
                section=course_info.get('section', ''),
                description=course_info.get('description', ''),
                teacher_id=teacher_id
            )
            self.db.add(course)
            self.db.commit()
        return course
    
    # Assignment Operations
    def get_or_create_assignment(self, google_assignment_id: str, course_id: uuid.UUID, assignment_info: Dict) -> Assignment:
        """Get or create an assignment from Google Classroom data"""
        assignment = self.db.query(Assignment).filter(Assignment.google_assignment_id == google_assignment_id).first()
        if not assignment:
            assignment = Assignment(
                google_assignment_id=google_assignment_id,
                course_id=course_id,
                title=assignment_info.get('title', f'Assignment {google_assignment_id}'),
                description=assignment_info.get('description', '')
            )
            self.db.add(assignment)
            self.db.commit()
        return assignment
    
    def get_assignment_by_google_id(self, google_assignment_id: str) -> Optional[Assignment]:
        """Get assignment by Google ID"""
        return self.db.query(Assignment).filter(Assignment.google_assignment_id == google_assignment_id).first()
    
    # Student Operations
    def get_or_create_student(self, google_student_id: str, course_id: uuid.UUID, student_info: Dict) -> Student:
        """Get or create a student from Google Classroom data"""
        student = self.db.query(Student).filter(
            Student.google_student_id == google_student_id,
            Student.course_id == course_id
        ).first()
        if not student:
            student = Student(
                google_student_id=google_student_id,
                course_id=course_id,
                name=student_info.get('name', f'Student {google_student_id}'),
                email=student_info.get('email', '')
            )
            self.db.add(student)
            self.db.commit()
        return student
    
    # Exam Operations
    def get_or_create_exam(self, assignment_id: uuid.UUID, exam_title: str) -> Exam:
        """Get or create an exam for an assignment"""
        exam = self.db.query(Exam).filter(Exam.assignment_id == assignment_id).first()
        if not exam:
            exam = Exam(
                assignment_id=assignment_id,
                title=exam_title,
                status="ACTIVE"
            )
            self.db.add(exam)
            self.db.commit()
        return exam
    
    # Submission Operations
    def get_or_create_submission(self, google_submission_id: str, exam_id: uuid.UUID, 
                               assignment_id: uuid.UUID, student_id: uuid.UUID, 
                               submission_info: Dict) -> Submission:
        """Get or create a submission from Google Classroom data"""
        submission = self.db.query(Submission).filter(Submission.google_submission_id == google_submission_id).first()
        if not submission:
            submission = Submission(
                google_submission_id=google_submission_id,
                exam_id=exam_id,
                assignment_id=assignment_id,
                student_id=student_id,
                google_drive_id=submission_info.get('google_drive_id'),
                local_file_path=submission_info.get('local_file_path'),
                status=submission_info.get('status', 'PENDING')
            )
            self.db.add(submission)
            self.db.commit()
        return submission
    
    def get_submissions_by_assignment(self, google_assignment_id: str) -> List[Submission]:
        """Get all submissions for an assignment"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return []
        
        return self.db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
    
    def get_submissions_by_status(self, google_assignment_id: str, statuses: List[str]) -> List[Submission]:
        """Get submissions by status for an assignment"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return []
        
        return self.db.query(Submission).filter(
            Submission.assignment_id == assignment.id,
            Submission.status.in_(statuses)
        ).all()
    
    def update_submission_status(self, submission_id: uuid.UUID, status: str, 
                               local_file_path: str = None) -> bool:
        """Update submission status and optionally file path"""
        submission = self.db.query(Submission).filter(Submission.id == submission_id).first()
        if submission:
            submission.status = status
            submission.updated_at = datetime.utcnow()
            if local_file_path:
                submission.local_file_path = local_file_path
            self.db.commit()
            return True
        return False
    
    def get_submission_by_google_id(self, google_submission_id: str) -> Optional[Submission]:
        """Get submission by Google submission ID"""
        return self.db.query(Submission).filter(Submission.google_submission_id == google_submission_id).first()
    
    def get_submission_by_student(self, google_assignment_id: str, google_student_id: str) -> Optional[Submission]:
        """Get submission by assignment and student"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return None
        
        return self.db.query(Submission).join(Student).filter(
            Submission.assignment_id == assignment.id,
            Student.google_student_id == google_student_id
        ).first()
    
    def get_submission_by_student_and_assignment(self, google_student_id: str, google_assignment_id: str, status: str = None) -> Optional[Submission]:
        """Get submission by student ID, assignment ID, and optionally status"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return None
        
        query = self.db.query(Submission).join(Student).filter(
            Submission.assignment_id == assignment.id,
            Student.google_student_id == google_student_id
        )
        
        if status:
            query = query.filter(Submission.status == status)
        
        return query.first()
    
    def get_submissions_by_student_and_assignment(self, google_student_id: str, google_assignment_id: str) -> List[Submission]:
        """Get all submissions by student ID and assignment ID"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return []
        
        return self.db.query(Submission).join(Student).filter(
            Submission.assignment_id == assignment.id,
            Student.google_student_id == google_student_id
        ).all()

    # Grading Task Operations
    def create_grading_task(self, task_id: str, assignment_id: uuid.UUID, 
                          grading_version: str = "v2", exam_id: uuid.UUID = None) -> GradingTask:
        """Create a new grading task"""
        task = GradingTask(
            task_id=task_id,
            assignment_id=assignment_id,
            exam_id=exam_id,
            grading_version=grading_version,
            status="PENDING"
        )
        self.db.add(task)
        self.db.commit()
        return task
    
    def get_grading_tasks_by_assignment(self, google_assignment_id: str) -> List[GradingTask]:
        """Get grading tasks for an assignment"""
        assignment = self.get_assignment_by_google_id(google_assignment_id)
        if not assignment:
            return []
        
        return self.db.query(GradingTask).filter(GradingTask.assignment_id == assignment.id).all()
    
    def update_grading_task(self, task_id: str, status: str = None, progress: int = None, 
                          message: str = None, result_summary: str = None) -> bool:
        """Update grading task status and progress"""
        task = self.db.query(GradingTask).filter(GradingTask.task_id == task_id).first()
        if task:
            if status:
                task.status = status
            if progress is not None:
                task.progress = progress
            if message:
                task.message = message
            if result_summary:
                task.result_summary = result_summary
            if status == "COMPLETED":
                task.completed_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
    
    # MongoDB Operations
    def store_answer_key(self, exam_id: str, answer_key_data: Dict[str, Any]) -> str:
        """Store answer key in MongoDB"""
        return self.mongo.store_answer_key(exam_id, answer_key_data)
    
    def get_answer_key(self, exam_id: str) -> Optional[Dict[str, Any]]:
        """Get answer key from MongoDB"""
        return self.mongo.get_answer_key(exam_id)
    
    def store_student_answers(self, submission_id: str, student_answers: Dict[str, Any]) -> str:
        """Store student answers in MongoDB and update submission"""
        mongo_id = self.mongo.store_student_answers(submission_id, student_answers)
        
        # Update submission with MongoDB document ID
        submission = self.db.query(Submission).filter(Submission.id == uuid.UUID(submission_id)).first()
        if submission:
            submission.student_answers_id = mongo_id
            submission.updated_at = datetime.utcnow()
            self.db.commit()
        
        return mongo_id
    
    def get_student_answers(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get student answers from MongoDB"""
        return self.mongo.get_student_answers(submission_id)
    
    def store_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> str:
        """Store grading results in MongoDB and update submission"""
        mongo_id = self.mongo.store_grading_results(submission_id, grading_results)
        
        # Update submission with MongoDB document ID and status
        submission = self.db.query(Submission).filter(Submission.id == uuid.UUID(submission_id)).first()
        if submission:
            submission.grading_results_id = mongo_id
            submission.status = "GRADED"
            submission.updated_at = datetime.utcnow()
            self.db.commit()
        
        return mongo_id
    
    def get_grading_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get grading results from MongoDB"""
        return self.mongo.get_grading_results(submission_id)
    
    def update_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> bool:
        """Update grading results in MongoDB"""
        return self.mongo.update_grading_results(submission_id, grading_results)
    
    def store_grade_edit(self, edit_data: Dict[str, Any]) -> str:
        """Store grade edit in MongoDB"""
        return self.mongo.store_grade_edit(edit_data)
    
    def store_training_data(self, training_data: Dict[str, Any]) -> str:
        """Store training data in MongoDB"""
        return self.mongo.store_training_data(training_data)
    
    # Utility Methods
    def get_submission_status_summary(self, google_assignment_id: str) -> Dict[str, int]:
        """Get submission status summary for an assignment"""
        submissions = self.get_submissions_by_assignment(google_assignment_id)
        
        summary = {
            "total": len(submissions),
            "pending": 0,
            "downloaded": 0,
            "ocr_complete": 0,
            "ocr_failed": 0,
            "graded": 0,
            "grading_failed": 0
        }
        
        for submission in submissions:
            status = submission.status.lower()
            if status in summary:
                summary[status] += 1
        
        return summary
    
    def migrate_json_file_to_mongo(self, file_path: Path, data_type: str, identifier: str) -> Optional[str]:
        """Migrate a JSON file to MongoDB"""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix == '.jsonl':
                    # Handle JSONL files
                    data = []
                    for line in f:
                        if line.strip():
                            data.append(json.loads(line))
                else:
                    # Handle regular JSON files
                    data = json.load(f)
            
            if data_type == "answer_key":
                return self.store_answer_key(identifier, data)
            elif data_type == "student_answers":
                return self.store_student_answers(identifier, data)
            elif data_type == "grading_results":
                return self.store_grading_results(identifier, {"results": data})
            
        except Exception as e:
            print(f"Error migrating {file_path}: {e}")
            return None
        
        return None

# Global service instance
def get_db_service(db_session: Session = None) -> DatabaseService:
    """Get database service instance"""
    return DatabaseService(db_session)

# Global instance for convenience
db_service = DatabaseService()
