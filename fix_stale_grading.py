#!/usr/bin/env python3
"""
Fix script to clear stale grading tasks and allow new grading
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, GradingTask, Assignment
from datetime import datetime, timedelta

def fix_stale_grading_tasks():
    """Clear stale grading tasks that are blocking new grading"""
    
    db = SessionLocal()
    try:
        coursework_id = '782918260130'
        
        # Find the assignment
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        
        if not assignment:
            print(f"Assignment not found for coursework {coursework_id}")
            return
            
        print(f"Found assignment: {assignment.title}")
        
        # Find all PENDING or RUNNING tasks
        blocking_tasks = db.query(GradingTask).filter(
            GradingTask.assignment_id == assignment.id,
            GradingTask.status.in_(["PENDING", "RUNNING"])
        ).all()
        
        print(f"Found {len(blocking_tasks)} blocking tasks")
        
        if not blocking_tasks:
            print("No blocking tasks found. Grading should work normally.")
            return
            
        # Check if tasks are stale (older than 30 minutes)
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        
        for task in blocking_tasks:
            task_age = datetime.utcnow() - task.created_at.replace(tzinfo=None)
            print(f"Task {task.id}: Status={task.status}, Age={task_age}")
            
            if task.created_at.replace(tzinfo=None) < cutoff_time:
                print(f"  -> STALE TASK: Marking as FAILED")
                task.status = "FAILED"
                task.message = "Task timed out and was automatically failed"
                task.updated_at = datetime.utcnow()
            else:
                print(f"  -> RECENT TASK: Leaving as-is")
                
        db.commit()
        print("✅ Fixed stale grading tasks")
        
        # Show remaining tasks
        remaining_blocking = db.query(GradingTask).filter(
            GradingTask.assignment_id == assignment.id,
            GradingTask.status.in_(["PENDING", "RUNNING"])
        ).count()
        
        print(f"Remaining blocking tasks: {remaining_blocking}")
        
        if remaining_blocking == 0:
            print("🎉 All blocking tasks cleared! New grading should work now.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fix_stale_grading_tasks()
