#!/usr/bin/env python3
"""
Diagnostic script to help identify why submissions are not showing up.
Run this script to check various aspects of the submission loading process.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_google_classroom_permissions():
    """Check if Google Classroom permissions are properly set up."""
    print("🔍 Checking Google Classroom API permissions...")
    
    try:
        from config import SCOPES
        print(f"✅ Required scopes: {len(SCOPES)}")
        for scope in SCOPES:
            print(f"   - {scope}")
        
        # Check if we have the necessary submission scopes
        required_submission_scopes = [
            "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
            "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
        ]
        
        missing_scopes = []
        for scope in required_submission_scopes:
            if scope not in SCOPES:
                missing_scopes.append(scope)
        
        if missing_scopes:
            print(f"❌ Missing required scopes: {missing_scopes}")
            return False
        else:
            print("✅ All required submission scopes are present")
            return True
            
    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
        return False

def check_database_state():
    """Check the current state of the database."""
    print("\n🔍 Checking database state...")
    
    try:
        from database import SessionLocal, Assignment, Course, Submission, Student
        
        with SessionLocal() as db:
            courses = db.query(Course).all()
            assignments = db.query(Assignment).all()
            students = db.query(Student).all()
            submissions = db.query(Submission).all()
            
            print(f"✅ Database connection successful")
            print(f"   - Courses: {len(courses)}")
            print(f"   - Assignments: {len(assignments)}")
            print(f"   - Students: {len(students)}")
            print(f"   - Submissions: {len(submissions)}")
            
            # Show recent assignments
            if assignments:
                print("\n📋 Recent assignments:")
                for assignment in assignments[-5:]:  # Show last 5
                    print(f"   - {assignment.google_assignment_id}: {assignment.title}")
            
            return True
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def check_server_status():
    """Check if the server is running."""
    print("\n🔍 Checking server status...")
    
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/api/submissions/test", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running and responding")
            return True
        else:
            print(f"❌ Server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server check failed: {e}")
        return False

def provide_debugging_steps():
    """Provide step-by-step debugging instructions."""
    print("\n🔧 Debugging Steps:")
    print("1. Check Google Classroom directly:")
    print("   - Go to Google Classroom")
    print("   - Navigate to your assignment")
    print("   - Verify that submissions are actually present")
    print("   - Check the submission states (TURNED_IN, CREATED, etc.)")
    
    print("\n2. Check the debug endpoint:")
    print("   - Go to: http://127.0.0.1:8000/api/submissions/debug-classroom/{course_id}/{coursework_id}")
    print("   - Replace {course_id} and {coursework_id} with actual values")
    print("   - This will show you exactly what Google Classroom API returns")
    
    print("\n3. Check user permissions:")
    print("   - Make sure you're logged in as a user with access to the submissions")
    print("   - Teachers can see all submissions, students can only see their own")
    print("   - Check if you have the right Google account selected")
    
    print("\n4. Check assignment type:")
    print("   - Some assignment types might not show submissions the same way")
    print("   - Make sure it's a regular assignment, not a quiz or announcement")
    
    print("\n5. Check timing:")
    print("   - New submissions might take a few minutes to appear in the API")
    print("   - Try refreshing after a few minutes")

def main():
    """Run all diagnostic checks."""
    print("🧪 AI Studio Submission Loading Diagnostic Tool")
    print("=" * 50)
    
    # Run all checks
    permissions_ok = check_google_classroom_permissions()
    database_ok = check_database_state()
    server_ok = check_server_status()
    
    print("\n" + "=" * 50)
    print("📊 Summary:")
    print(f"   Google Classroom Permissions: {'✅' if permissions_ok else '❌'}")
    print(f"   Database: {'✅' if database_ok else '❌'}")
    print(f"   Server: {'✅' if server_ok else '❌'}")
    
    if not all([permissions_ok, database_ok, server_ok]):
        print("\n❌ Some checks failed. Please fix the issues above first.")
    else:
        print("\n✅ All basic checks passed. The issue might be with:")
        print("   - Google Classroom API not returning submissions")
        print("   - User permissions")
        print("   - Assignment configuration")
        print("   - Timing issues")
    
    provide_debugging_steps()

if __name__ == "__main__":
    main()
