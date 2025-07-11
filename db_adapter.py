"""
Database adapter for transitioning from old to new database schema.
This module provides compatibility functions to ease the migration.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid

from database import Submission, Student, Assignment, get_db
from db_service import DatabaseService

class LegacyDatabaseAdapter:
    """Adapter class to maintain compatibility with old database calls"""
    
    def __init__(self, db_session: Session = None):
        self.db_service = DatabaseService(db_session)
        self.db = self.db_service.db
    
    def get_submissions_by_coursework_id(self, coursework_id: str) -> List[Submission]:
        """Get submissions by coursework ID (legacy compatibility)"""
        return self.db_service.get_submissions_by_assignment(coursework_id)
    
    def get_submission_by_google_submission_id(self, google_submission_id: str) -> Optional[Submission]:
        """Get submission by Google submission ID (legacy compatibility)"""
        return self.db_service.get_submission_by_google_id(google_submission_id)
    
    def create_submission_record_from_legacy(self, legacy_data: Dict[str, Any]) -> Optional[Submission]:
        """Create submission from legacy data format"""
        try:
            # Extract data from legacy format
            google_submission_id = legacy_data.get('google_submission_id')
            course_id = legacy_data.get('course_id')
            coursework_id = legacy_data.get('coursework_id')
            student_id = legacy_data.get('student_id')
            student_name = legacy_data.get('student_name')
            google_drive_id = legacy_data.get('google_drive_id')
            local_file_path = legacy_data.get('local_file_path')
            status = legacy_data.get('status', 'PENDING')
            
            # Get or create course (use coursework_id as course for now)
            course = self.db_service.get_or_create_course(
                course_id or coursework_id,
                {'name': f'Course {course_id}'},
                # Use first user as teacher (this is a migration hack)
                uuid.uuid4()  # You'll need to handle this properly
            )
            
            # Get or create assignment
            assignment = self.db_service.get_or_create_assignment(
                coursework_id,
                course.id,
                {'title': f'Assignment {coursework_id}'}
            )
            
            # Get or create student
            student = self.db_service.get_or_create_student(
                student_id,
                course.id,
                {'name': student_name}
            )
            
            # Get or create exam
            exam = self.db_service.get_or_create_exam(
                assignment.id,
                f'Exam for {assignment.title}'
            )
            
            # Create submission
            submission = self.db_service.get_or_create_submission(
                google_submission_id,
                exam.id,
                assignment.id,
                student.id,
                {
                    'google_drive_id': google_drive_id,
                    'local_file_path': local_file_path,
                    'status': status
                }
            )
            
            return submission
            
        except Exception as e:
            print(f"Error creating submission from legacy data: {e}")
            return None
    
    def update_submission_status_legacy(self, google_submission_id: str, 
                                      status: str, local_file_path: str = None) -> bool:
        """Update submission status (legacy compatibility)"""
        submission = self.get_submission_by_google_submission_id(google_submission_id)
        if submission:
            return self.db_service.update_submission_status(
                submission.id, status, local_file_path
            )
        return False
    
    def get_student_by_google_id_legacy(self, google_student_id: str, coursework_id: str) -> Optional[Student]:
        """Get student by Google ID within a coursework context"""
        assignment = self.db_service.get_assignment_by_google_id(coursework_id)
        if not assignment:
            return None
        
        return self.db.query(Student).filter(
            Student.google_student_id == google_student_id,
            Student.course_id == assignment.course_id
        ).first()
    
    def get_assignment_by_google_id_legacy(self, google_assignment_id: str) -> Optional[Assignment]:
        """Get assignment by Google ID (legacy compatibility)"""
        return self.db_service.get_assignment_by_google_id(google_assignment_id)
    
    def close(self):
        """Close the database connection"""
        self.db_service.close()

# Legacy compatibility functions
def get_legacy_adapter(db_session: Session = None) -> LegacyDatabaseAdapter:
    """Get legacy database adapter"""
    return LegacyDatabaseAdapter(db_session)
