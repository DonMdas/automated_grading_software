#!/usr/bin/env python3
"""
Simple database inspection script.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Assignment, Submission, Student, Course

def inspect_database():
    """Inspect the current database state."""
    print("🔍 Inspecting database state...")
    
    try:
        with SessionLocal() as db:
            # Check courses
            courses = db.query(Course).all()
            print(f"\n📚 Courses: {len(courses)}")
            for course in courses:
                print(f"   - {course.google_course_id}: {course.name}")
            
            # Check assignments
            assignments = db.query(Assignment).all()
            print(f"\n📋 Assignments: {len(assignments)}")
            for assignment in assignments:
                print(f"   - {assignment.google_assignment_id}: {assignment.title}")
                
                # Check submissions for this assignment
                submissions = db.query(Submission).filter(
                    Submission.assignment_id == assignment.id
                ).all()
                print(f"     Submissions: {len(submissions)}")
                
                for sub in submissions:
                    student_name = sub.student.name if sub.student else "Unknown"
                    print(f"       - {student_name}: {sub.status}")
            
            # Check students
            students = db.query(Student).all()
            print(f"\n👥 Students: {len(students)}")
            for student in students:
                print(f"   - {student.google_student_id}: {student.name}")
            
            # Check submissions
            submissions = db.query(Submission).all()
            print(f"\n📝 All Submissions: {len(submissions)}")
            for sub in submissions:
                student_name = sub.student.name if sub.student else "Unknown"
                print(f"   - {sub.google_submission_id}: {student_name} - {sub.status}")
            
            return True
    except Exception as e:
        print(f"❌ Database inspection failed: {e}")
        return False

if __name__ == "__main__":
    inspect_database()
