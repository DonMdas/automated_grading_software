#!/usr/bin/env python3
"""
Update MongoDB with processed answer key from file system.
"""

import sys
import json
sys.path.insert(0, '/home/don/Documents/Internship/aistudioversion')

from db_service import DatabaseService

def update_mongo_with_processed_answer_key():
    """Update MongoDB with the processed answer key from file system."""
    print("Updating MongoDB with processed answer key...")
    
    # Load the processed answer key from file system
    processed_file = "/home/don/Documents/Internship/aistudioversion/server_data/782918260130/answer_key_processed.json"
    
    try:
        with open(processed_file, 'r') as f:
            processed_data = json.load(f)
        
        print(f"✅ Loaded processed answer key with {len(processed_data)} questions")
        
        # Check structure of first question
        first_q_key = list(processed_data.keys())[0]
        first_q = processed_data[first_q_key]
        
        print(f"First question structure:")
        print(f"  Keys: {list(first_q.keys())}")
        
        if "structure" in first_q:
            structure_keys = list(first_q["structure"].keys())
            print(f"  Structure components: {structure_keys}")
            
            # Show first component
            if structure_keys:
                first_comp = first_q["structure"][structure_keys[0]]
                print(f"  First component type: {type(first_comp)}")
                if isinstance(first_comp, dict) and "content" in first_comp:
                    print(f"  First component content: {first_comp['content'][:100]}...")
        
        # Update MongoDB
        db_service = DatabaseService()
        try:
            exam_id = "782918260130"
            result = db_service.store_answer_key(exam_id, processed_data)
            print(f"✅ Answer key stored in MongoDB with result: {result}")
            
            # Try to retrieve and verify
            retrieved = db_service.get_answer_key(exam_id)
            if retrieved:
                print(f"✅ Answer key retrieved successfully")
                first_retrieved = retrieved[first_q_key]
                if "structure" in first_retrieved:
                    print(f"✅ Structure components preserved in MongoDB")
                    return True
            else:
                print("❌ Failed to retrieve answer key from MongoDB")
                return False
                
        except Exception as e:
            print(f"❌ MongoDB error: {e}")
            return False
        finally:
            db_service.close()
            
    except Exception as e:
        print(f"❌ Error loading processed file: {e}")
        return False

if __name__ == "__main__":
    success = update_mongo_with_processed_answer_key()
    print(f"\nUpdate {'SUCCESSFUL' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
