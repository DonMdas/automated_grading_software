#!/usr/bin/env python3
"""
Manual grading trigger script
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uuid
from database import SessionLocal, Assignment
from db_service import get_db_service
from background_tasks import process_grading_in_background_v2

def manual_trigger_grading():
    """Manually trigger grading for a specific coursework"""
    
    coursework_id = '782918260130'
    grading_version = 'v2'
    
    db = SessionLocal()
    db_service = get_db_service(db)
    
    try:
        print(f"🚀 Manually triggering grading for coursework {coursework_id}")
        
        # Find the assignment
        assignment = db.query(Assignment).filter(Assignment.google_assignment_id == coursework_id).first()
        
        if not assignment:
            print(f"❌ Assignment not found for coursework {coursework_id}")
            return
            
        print(f"✅ Found assignment: {assignment.title}")
        
        # Check OCR complete submissions
        ocr_complete_submissions = db_service.get_submissions_by_status(coursework_id, ["OCR_COMPLETE"])
        print(f"📋 Found {len(ocr_complete_submissions)} OCR-complete submissions")
        
        if len(ocr_complete_submissions) == 0:
            print("❌ No OCR-complete submissions found")
            return
            
        # Clear any stale tasks first
        grading_tasks = db_service.get_grading_tasks_by_assignment(coursework_id)
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        
        stale_tasks = [
            task for task in grading_tasks 
            if task.status in ["PENDING", "RUNNING"] and task.created_at.replace(tzinfo=None) < cutoff_time
        ]
        
        if stale_tasks:
            print(f"🧹 Clearing {len(stale_tasks)} stale tasks...")
            for task in stale_tasks:
                db_service.update_grading_task(task.id, "FAILED", message="Task timed out and was manually cleared")
                print(f"   Cleared task {task.id}")
        
        # Check for any remaining blocking tasks
        remaining_tasks = db_service.get_grading_tasks_by_assignment(coursework_id)
        blocking_tasks = [task for task in remaining_tasks if task.status in ["PENDING", "RUNNING"]]
        
        if blocking_tasks:
            print(f"⚠️  Found {len(blocking_tasks)} still-active grading tasks:")
            for task in blocking_tasks:
                print(f"   Task {task.id}: {task.status} (Created: {task.created_at})")
                
            print("❌ Cannot start new grading while other tasks are active")
            return
            
        # Create new grading task
        task_id = str(uuid.uuid4())
        exam_id = assignment.exams[0].id if assignment.exams else None
        
        grading_task = db_service.create_grading_task(
            task_id=task_id,
            assignment_id=assignment.id,
            grading_version=grading_version,
            exam_id=exam_id
        )
        
        print(f"✅ Created new grading task: {task_id}")
        
        # Start grading immediately
        print(f"🔄 Starting grading process...")
        process_grading_in_background_v2(task_id, coursework_id, grading_version, db)
        
        print(f"🎉 Grading process initiated!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_service.close()

if __name__ == "__main__":
    manual_trigger_grading()
