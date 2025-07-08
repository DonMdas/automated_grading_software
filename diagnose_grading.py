#!/usr/bin/env python3
"""
Diagnostic script for grading task status
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, GradingTask, Submission, Assignment
from datetime import datetime

def diagnose_grading_tasks():
    """Diagnose grading task issues"""
    print("🔍 Diagnosing grading task status...")
    
    db = SessionLocal()
    try:
        coursework_id = '782918260130'
        
        # Find the assignment
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        
        if assignment:
            print(f"✅ Found assignment: {assignment.title} (ID: {assignment.id})")
            
            # Get all grading tasks for this assignment
            grading_tasks = db.query(GradingTask).filter(GradingTask.assignment_id == assignment.id).order_by(GradingTask.created_at.desc()).all()
            print(f"📋 Found {len(grading_tasks)} grading tasks:")
            
            for i, task in enumerate(grading_tasks):
                print(f"  {i+1}. Task ID: {task.id}")
                print(f"     Status: {task.status}")
                print(f"     Progress: {task.progress}%")
                print(f"     Created: {task.created_at}")
                print(f"     Updated: {task.updated_at}")
                print(f"     Message: {task.message}")
                
                # Check if task is blocking
                if task.status in ["PENDING", "RUNNING"]:
                    print(f"     ⚠️  BLOCKING TASK - This task is preventing new grading!")
                    
                    # Check how old it is
                    time_diff = datetime.utcnow() - task.created_at.replace(tzinfo=None)
                    print(f"     Age: {time_diff}")
                    
                    if time_diff.total_seconds() > 1800:  # 30 minutes
                        print(f"     🚨 STALE TASK - This task is over 30 minutes old!")
                
                print("     ---")
                
            # Check submissions
            submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
            ocr_complete = [s for s in submissions if s.status == "OCR_COMPLETE"]
            graded = [s for s in submissions if s.status == "GRADED"]
            
            print(f"📊 Submission status:")
            print(f"  Total submissions: {len(submissions)}")
            print(f"  OCR Complete: {len(ocr_complete)}")
            print(f"  Graded: {len(graded)}")
            
            # Check for blocking conditions
            blocking_tasks = [t for t in grading_tasks if t.status in ["PENDING", "RUNNING"]]
            if blocking_tasks:
                print(f"\\n🚨 ISSUE FOUND: {len(blocking_tasks)} tasks are blocking new grading:")
                for task in blocking_tasks:
                    print(f"  - Task {task.id}: {task.status} (Created: {task.created_at})")
                    
                print(f"\\n💡 SOLUTION: Clear these tasks to allow new grading")
                return blocking_tasks
            else:
                print(f"\\n✅ No blocking tasks found")
                if len(ocr_complete) >= 3:
                    print(f"   Should be able to start new grading automatically")
                else:
                    print(f"   Need at least 3 OCR complete submissions to auto-start grading")
                    
        else:
            print(f"❌ Assignment not found for coursework {coursework_id}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_grading_tasks()
