#!/usr/bin/env python3
"""
Data migration script from SQLite to PostgreSQL for the AI Studio application.
This script migrates existing data from the old SQLite database to the new PostgreSQL database.
"""

import sys
import os
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    SessionLocal, User, UserSession, Course, Assignment, Student, 
    Submission, Exam, GradingTask, mongo_manager
)

def migrate_users(sqlite_conn, pg_session: Session):
    """Migrate users from SQLite to PostgreSQL"""
    print("📊 Migrating users...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, email, full_name, role, google_credentials, created_at, updated_at FROM users")
    users = cursor.fetchall()
    
    user_id_mapping = {}
    
    for user in users:
        old_id, email, full_name, role, google_credentials, created_at, updated_at = user
        
        # Generate new UUID
        new_id = uuid.uuid4()
        user_id_mapping[old_id] = new_id
        
        # Create new user
        new_user = User(
            id=new_id,
            email=email,
            full_name=full_name,
            role=role,
            google_credentials=google_credentials,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else datetime.utcnow()
        )
        
        pg_session.add(new_user)
    
    pg_session.commit()
    print(f"✅ Migrated {len(users)} users")
    return user_id_mapping

def migrate_user_sessions(sqlite_conn, pg_session: Session, user_id_mapping: dict):
    """Migrate user sessions from SQLite to PostgreSQL"""
    print("📊 Migrating user sessions...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, session_id, user_id, expires_at, created_at FROM user_sessions")
    sessions = cursor.fetchall()
    
    for session in sessions:
        old_id, session_id, user_id, expires_at, created_at = session
        
        if user_id not in user_id_mapping:
            print(f"⚠️  Skipping session {session_id} - user {user_id} not found")
            continue
        
        # Create new session
        new_session = UserSession(
            id=uuid.uuid4(),
            session_id=session_id,
            user_id=user_id_mapping[user_id],
            expires_at=datetime.fromisoformat(expires_at),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
        )
        
        pg_session.add(new_session)
    
    pg_session.commit()
    print(f"✅ Migrated {len(sessions)} user sessions")

def migrate_assignments_and_create_courses(sqlite_conn, pg_session: Session, user_id_mapping: dict):
    """Migrate assignments and create courses from SQLite to PostgreSQL"""
    print("📊 Migrating assignments and creating courses...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, google_id, name FROM assignments")
    assignments = cursor.fetchall()
    
    # Create a default course for migrated assignments
    default_teacher_id = list(user_id_mapping.values())[0] if user_id_mapping else uuid.uuid4()
    
    assignment_id_mapping = {}
    course_id_mapping = {}
    
    for assignment in assignments:
        old_id, google_id, name = assignment
        
        # Create a course for each assignment (since we don't have course info in old schema)
        course_id = uuid.uuid4()
        course_id_mapping[google_id] = course_id
        
        new_course = Course(
            id=course_id,
            google_course_id=f"MIGRATED_{google_id}",
            name=f"Course for {name}",
            teacher_id=default_teacher_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        pg_session.add(new_course)
        
        # Create assignment
        assignment_id = uuid.uuid4()
        assignment_id_mapping[old_id] = assignment_id
        
        new_assignment = Assignment(
            id=assignment_id,
            google_assignment_id=google_id,
            course_id=course_id,
            title=name or f"Assignment {google_id}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        pg_session.add(new_assignment)
    
    pg_session.commit()
    print(f"✅ Migrated {len(assignments)} assignments and created {len(assignments)} courses")
    return assignment_id_mapping, course_id_mapping

def migrate_students(sqlite_conn, pg_session: Session, course_id_mapping: dict):
    """Migrate students from SQLite to PostgreSQL"""
    print("📊 Migrating students...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, google_id, name FROM students")
    students = cursor.fetchall()
    
    student_id_mapping = {}
    
    for student in students:
        old_id, google_id, name = student
        
        # Assign to the first course (since we don't have course info in old schema)
        course_id = list(course_id_mapping.values())[0] if course_id_mapping else uuid.uuid4()
        
        new_id = uuid.uuid4()
        student_id_mapping[old_id] = new_id
        
        new_student = Student(
            id=new_id,
            google_student_id=google_id,
            course_id=course_id,
            name=name or f"Student {google_id}",
            created_at=datetime.utcnow()
        )
        
        pg_session.add(new_student)
    
    pg_session.commit()
    print(f"✅ Migrated {len(students)} students")
    return student_id_mapping

def migrate_submissions(sqlite_conn, pg_session: Session, assignment_id_mapping: dict, student_id_mapping: dict):
    """Migrate submissions from SQLite to PostgreSQL"""
    print("📊 Migrating submissions...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("""
        SELECT id, google_submission_id, course_id, coursework_id, student_id, 
               student_name, google_drive_id, local_file_path, status, created_at
        FROM submissions
    """)
    submissions = cursor.fetchall()
    
    submission_id_mapping = {}
    
    for submission in submissions:
        (old_id, google_submission_id, course_id, coursework_id, student_id, 
         student_name, google_drive_id, local_file_path, status, created_at) = submission
        
        # Find corresponding assignment
        assignment_id = None
        for old_assign_id, new_assign_id in assignment_id_mapping.items():
            if str(old_assign_id) == str(coursework_id):
                assignment_id = new_assign_id
                break
        
        if not assignment_id:
            print(f"⚠️  Skipping submission {google_submission_id} - assignment not found")
            continue
        
        # Create exam for the assignment
        exam_id = uuid.uuid4()
        exam = Exam(
            id=exam_id,
            assignment_id=assignment_id,
            title=f"Exam for {student_name}",
            status="ACTIVE",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        pg_session.add(exam)
        
        # Find corresponding student
        student_db_id = None
        for old_student_id, new_student_id in student_id_mapping.items():
            if str(old_student_id) == str(student_id):
                student_db_id = new_student_id
                break
        
        if not student_db_id:
            # Create a new student if not found
            student_db_id = uuid.uuid4()
            course_id = list(pg_session.query(Assignment).filter_by(id=assignment_id).first().course_id)
            new_student = Student(
                id=student_db_id,
                google_student_id=student_id,
                course_id=course_id,
                name=student_name or f"Student {student_id}",
                created_at=datetime.utcnow()
            )
            pg_session.add(new_student)
        
        # Create submission
        new_id = uuid.uuid4()
        submission_id_mapping[old_id] = new_id
        
        new_submission = Submission(
            id=new_id,
            google_submission_id=google_submission_id,
            exam_id=exam_id,
            assignment_id=assignment_id,
            student_id=student_db_id,
            google_drive_id=google_drive_id,
            local_file_path=local_file_path,
            status=status,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        pg_session.add(new_submission)
    
    pg_session.commit()
    print(f"✅ Migrated {len(submissions)} submissions")
    return submission_id_mapping

def migrate_grading_tasks(sqlite_conn, pg_session: Session, assignment_id_mapping: dict):
    """Migrate grading tasks from SQLite to PostgreSQL"""
    print("📊 Migrating grading tasks...")
    
    cursor = sqlite_conn.cursor()
    cursor.execute("""
        SELECT id, task_id, coursework_id, grading_version, status, progress, 
               message, result, created_at, completed_at
        FROM grading_tasks
    """)
    tasks = cursor.fetchall()
    
    for task in tasks:
        (old_id, task_id, coursework_id, grading_version, status, progress, 
         message, result, created_at, completed_at) = task
        
        # Find corresponding assignment
        assignment_id = None
        for old_assign_id, new_assign_id in assignment_id_mapping.items():
            if str(old_assign_id) == str(coursework_id):
                assignment_id = new_assign_id
                break
        
        if not assignment_id:
            print(f"⚠️  Skipping grading task {task_id} - assignment not found")
            continue
        
        new_task = GradingTask(
            id=uuid.uuid4(),
            task_id=task_id,
            assignment_id=assignment_id,
            grading_version=grading_version,
            status=status,
            progress=progress,
            message=message,
            result_summary=result,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
            completed_at=datetime.fromisoformat(completed_at) if completed_at else None
        )
        
        pg_session.add(new_task)
    
    pg_session.commit()
    print(f"✅ Migrated {len(tasks)} grading tasks")

def migrate_json_files_to_mongodb(server_data_dir: str, submission_id_mapping: dict):
    """Migrate JSON files from file system to MongoDB"""
    print("📊 Migrating JSON files to MongoDB...")
    
    server_data_path = Path(server_data_dir)
    if not server_data_path.exists():
        print(f"⚠️  Server data directory {server_data_dir} not found")
        return
    
    migrated_files = 0
    
    for coursework_dir in server_data_path.iterdir():
        if not coursework_dir.is_dir():
            continue
            
        # Migrate answer keys
        answer_key_file = coursework_dir / "answer_key.json"
        if answer_key_file.exists():
            try:
                with open(answer_key_file, 'r') as f:
                    answer_key_data = json.load(f)
                    
                mongo_manager.store_answer_key(str(coursework_dir.name), answer_key_data)
                migrated_files += 1
                print(f"✅ Migrated answer key for {coursework_dir.name}")
            except Exception as e:
                print(f"⚠️  Failed to migrate answer key for {coursework_dir.name}: {e}")
        
        # Migrate student answers
        student_ocr_dir = coursework_dir / "student_submissions_ocr"
        if student_ocr_dir.exists():
            for student_file in student_ocr_dir.glob("*.json"):
                try:
                    with open(student_file, 'r') as f:
                        student_data = json.load(f)
                        
                    submission_id = student_file.stem  # filename without extension
                    mongo_manager.store_student_answers(submission_id, student_data)
                    migrated_files += 1
                    print(f"✅ Migrated student answers for {submission_id}")
                except Exception as e:
                    print(f"⚠️  Failed to migrate student answers for {student_file.name}: {e}")
        
        # Migrate grading results
        prodigy_dir = coursework_dir / "prodigy_data"
        if prodigy_dir.exists():
            for result_file in prodigy_dir.glob("*_prodigy.jsonl"):
                try:
                    results = []
                    with open(result_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                results.append(json.loads(line))
                    
                    submission_id = result_file.stem.replace("_prodigy", "")
                    mongo_manager.store_grading_results(submission_id, {"results": results})
                    migrated_files += 1
                    print(f"✅ Migrated grading results for {submission_id}")
                except Exception as e:
                    print(f"⚠️  Failed to migrate grading results for {result_file.name}: {e}")
    
    print(f"✅ Migrated {migrated_files} JSON files to MongoDB")

def main():
    """Main migration function"""
    print("🚀 Starting data migration from SQLite to PostgreSQL/MongoDB...")
    print("=" * 70)
    
    # Check if SQLite database exists
    sqlite_path = "app_data.db"
    if not Path(sqlite_path).exists():
        print(f"❌ SQLite database {sqlite_path} not found")
        return False
    
    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        
        # Connect to PostgreSQL
        pg_session = SessionLocal()
        
        # Perform migrations
        user_id_mapping = migrate_users(sqlite_conn, pg_session)
        migrate_user_sessions(sqlite_conn, pg_session, user_id_mapping)
        assignment_id_mapping, course_id_mapping = migrate_assignments_and_create_courses(
            sqlite_conn, pg_session, user_id_mapping
        )
        student_id_mapping = migrate_students(sqlite_conn, pg_session, course_id_mapping)
        submission_id_mapping = migrate_submissions(
            sqlite_conn, pg_session, assignment_id_mapping, student_id_mapping
        )
        migrate_grading_tasks(sqlite_conn, pg_session, assignment_id_mapping)
        
        # Migrate JSON files to MongoDB
        migrate_json_files_to_mongodb("server_data", submission_id_mapping)
        
        print("\n✅ Data migration completed successfully!")
        print("📊 Migration Summary:")
        print(f"   - {len(user_id_mapping)} users migrated")
        print(f"   - {len(assignment_id_mapping)} assignments migrated")
        print(f"   - {len(course_id_mapping)} courses created")
        print(f"   - {len(student_id_mapping)} students migrated")
        print(f"   - {len(submission_id_mapping)} submissions migrated")
        print("   - JSON files migrated to MongoDB")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'pg_session' in locals():
            pg_session.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
