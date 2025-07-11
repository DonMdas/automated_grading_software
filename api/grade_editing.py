"""
Grade editing API endpoints for the AI Studio application.
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import get_current_user
from config import SERVER_DATA_DIR
from db_service import db_service

router = APIRouter()

@router.post("/api/results/edit-grade")
async def edit_grade(
    edit_data: dict,
    current_user = Depends(get_current_user)
):
    """Edit a grade for a specific question and manage training data buffer"""
    try:
        coursework_id = edit_data.get('coursework_id')
        student_id = edit_data.get('student_id')
        question_id = edit_data.get('question_id')
        old_grade = float(edit_data.get('old_grade', 0))
        new_grade = float(edit_data.get('new_grade'))
        reason = edit_data.get('reason', '')
        
        if not all([coursework_id, student_id, question_id]):
            response_data = {
                "error": "Missing required fields",
                "success": False
            }
            return JSONResponse(content=response_data)
        
        if not (0 <= new_grade <= 10):
            response_data = {
                "error": "Grade must be between 0 and 10",
                "success": False
            }
            return JSONResponse(content=response_data)
        
        # Get submission from database
        submission = db_service.get_submission_by_student_and_assignment(
            student_id, coursework_id, status="GRADED"
        )
        
        if not submission:
            response_data = {
                "error": "Graded submission not found",
                "success": False
            }
            return JSONResponse(content=response_data)
        
        # Update the grade in MongoDB
        await update_grade_in_mongo(str(submission.id), question_id, new_grade)
        
        # Extract features and store in buffer
        await store_grade_edit_in_buffer(str(submission.id), student_id, question_id, old_grade, new_grade, reason)
        
        # Check if buffer is full and retrain if needed
        await check_and_retrain_model()
        
        response_data = {
            "message": "Grade updated successfully",
            "old_grade": old_grade,
            "new_grade": new_grade,
            "question_id": question_id,
            "success": True
        }
        return JSONResponse(content=response_data)
        
    except Exception as e:
        response_data = {
            "error": f"Failed to update grade: {str(e)}",
            "success": False
        }
        return JSONResponse(content=response_data)

async def update_grade_in_mongo(submission_id: str, question_id: str, new_grade: float):
    """Update the grade in MongoDB"""
    try:
        # Get grading results from MongoDB
        grading_results = db_service.get_grading_results(submission_id)
        
        if not grading_results:
            raise ValueError("Grading results not found")
        
        # Update the specific question's grade
        results_list = grading_results.get('results', []) if isinstance(grading_results, dict) else grading_results
        updated = False
        
        for result in results_list:
            if result.get("meta", {}).get("id") == question_id:
                result["meta"]["predicted_grade"] = str(int(new_grade))
                result["meta"]["manual_grade"] = new_grade
                result["meta"]["grade_edited"] = True
                result["meta"]["edit_timestamp"] = datetime.now().isoformat()
                updated = True
                break
        
        if not updated:
            raise ValueError(f"Question {question_id} not found in grading results")
        
        # Update in MongoDB
        db_service.update_grading_results(submission_id, grading_results)
        
    except Exception as e:
        raise ValueError(f"Failed to update grade: {str(e)}")

async def store_grade_edit_in_buffer(submission_id: str, student_id: str, question_id: str, old_grade: float, new_grade: float, reason: str):
    """Store the grade edit in buffer with extracted features"""
    try:
        # Load the grading results to extract features
        grading_results = db_service.get_grading_results(submission_id)
        
        features = None
        results_list = grading_results.get('results', []) if isinstance(grading_results, dict) else grading_results
        
        for result in results_list:
            if result.get("meta", {}).get("id") == question_id:
                # Extract features in the same order as used for prediction
                features = extract_features_for_training(result)
                break
        
        if features is None:
            raise ValueError("Could not extract features for training")
        
        # Store in MongoDB training data collection
        grade_edit_data = {
            'submission_id': submission_id,
            'student_id': student_id,
            'question_id': question_id,
            'old_grade': old_grade,
            'new_grade': new_grade,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            **features  # Add all extracted features
        }
        
        db_service.store_grade_edit(grade_edit_data)
        
    except Exception as e:
        print(f"Error storing grade edit in buffer: {str(e)}")
        # Don't raise exception here to not break the grade update

def extract_features_for_training(result):
    """Extract features from result in the same order as used for prediction"""
    meta = result.get("meta", {})
    
    # Only the required features for training
    features = {
        'tfidf_similarity': meta.get('tfidf_similarity_score', 0),
        'full_similarity_score': meta.get('full_similarity_score', 0),
        'mean_similarity_score': meta.get('mean_structure_similarity_score', 0)
    }
    
    return features

async def check_and_retrain_model():
    """Check if buffer has 100 entries and retrain model if needed"""
    try:
        # Get count of grade edits from MongoDB
        edit_count = db_service.count_grade_edits()
        
        if edit_count >= 100:
            # Export data for retraining
            await export_training_data()
            
            # Clear the buffer after exporting
            db_service.clear_grade_edits_buffer()
            
            print(f"Exported {edit_count} grade edits for model retraining")
            
    except Exception as e:
        print(f"Error checking and retraining model: {str(e)}")

async def export_training_data():
    """Export grade edits to CSV for model retraining"""
    try:
        # Get all grade edits from MongoDB
        grade_edits = db_service.get_all_grade_edits()
        
        if not grade_edits:
            return
        
        # Create training data directory
        training_dir = Path("training_data")
        training_dir.mkdir(exist_ok=True)
        
        # Convert to DataFrame
        df = pd.DataFrame(grade_edits)
        
        # Save main training data
        main_file = training_dir / "grade_training_data.csv"
        if main_file.exists():
            existing_df = pd.read_csv(main_file)
            df = pd.concat([existing_df, df], ignore_index=True)
        
        df.to_csv(main_file, index=False)
        print(f"Exported {len(df)} training samples to {main_file}")
        
    except Exception as e:
        print(f"Error exporting training data: {str(e)}")

