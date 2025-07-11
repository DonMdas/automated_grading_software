#!/usr/bin/env python3
"""
Test script to check if grading results are being stored in MongoDB
"""

import sys
from db_service import DatabaseService
from database import SessionLocal
from config_v2 import *

def check_grading_results():
    """Check if grading results exist in MongoDB"""
    print("Checking grading results in MongoDB...")
    
    try:
        db = SessionLocal()
        db_service = DatabaseService(db)
        mongo = db_service.mongo
        
        # Count total documents in grading_results collection
        total_results = mongo.db.grading_results.count_documents({})
        print(f"Total grading results in collection: {total_results}")
        
        if total_results > 0:
            # Get a sample result
            sample_result = mongo.db.grading_results.find_one({})
            if sample_result:
                print(f"Sample result structure:")
                print(f"  - Submission ID: {sample_result.get('submission_id', 'N/A')}")
                print(f"  - Result keys: {list(sample_result.get('grading_results', {}).keys())}")
                print(f"  - Created at: {sample_result.get('created_at', 'N/A')}")
                
                # Check if results have the expected structure
                grading_data = sample_result.get('grading_results', {})
                if 'results' in grading_data:
                    results_list = grading_data['results']
                    print(f"  - Number of questions graded: {len(results_list) if isinstance(results_list, list) else 'N/A'}")
                    if isinstance(results_list, list) and len(results_list) > 0:
                        print(f"  - Sample question result keys: {list(results_list[0].keys()) if results_list[0] else 'N/A'}")
        
        # Check answer keys
        total_answer_keys = mongo.db.answer_keys.count_documents({})
        print(f"Total answer keys in collection: {total_answer_keys}")
        
        # Check student answers
        total_student_answers = mongo.db.student_answers.count_documents({})
        print(f"Total student answers in collection: {total_student_answers}")
        
        db.close()
        return total_results > 0
        
    except Exception as e:
        print(f"Error checking MongoDB: {e}")
        return False

if __name__ == "__main__":
    print("=== Checking MongoDB Grading Results ===")
    has_results = check_grading_results()
    if has_results:
        print("\n✅ Grading results found in MongoDB")
    else:
        print("\n❌ No grading results found in MongoDB")
        print("   This could mean:")
        print("   1. Grading hasn't completed yet")
        print("   2. Grading failed before storing results")
        print("   3. Results are being stored with a different structure")
