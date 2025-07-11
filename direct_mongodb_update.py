#!/usr/bin/env python3
"""
Simple MongoDB update using Python pymongo.
"""

import json
import sys
import os
from datetime import datetime

# Try to import pymongo directly
try:
    from pymongo import MongoClient
    print("✅ pymongo imported successfully")
except ImportError:
    print("❌ pymongo not available, installing...")
    os.system("pip install pymongo")
    from pymongo import MongoClient

def direct_mongodb_update():
    """Update MongoDB directly using pymongo."""
    
    print("Updating MongoDB directly with pymongo...")
    
    processed_file = "/home/don/Documents/Internship/aistudioversion/server_data/782918260130/answer_key_processed.json"
    
    try:
        # Load the processed answer key
        with open(processed_file, 'r') as f:
            processed_data = json.load(f)
        
        print(f"✅ Loaded processed answer key with {len(processed_data)} questions")
        
        # Check question 14
        if "14" in processed_data:
            q14 = processed_data["14"]
            print(f"✅ Question 14 verification:")
            print(f"  Question: {q14.get('question', 'Not found')}")
            print(f"  Answer: {q14.get('answer', 'Not found')[:100]}...")
            
            structure = q14.get("structure", {})
            print(f"  Structure type: {type(structure)}")
            print(f"  Structure keys: {list(structure.keys()) if isinstance(structure, dict) else 'Not a dict'}")
            
            if isinstance(structure, dict):
                for key, value in list(structure.items())[:2]:  # Show first 2 components
                    if isinstance(value, dict) and "content" in value:
                        print(f"    {key}: {value['content'][:50]}...")
            
        else:
            print("❌ Question 14 not found")
            return False
        
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=5000)
        db = client['grading_system_mongo']
        
        # Test connection
        client.admin.command('ping')
        print("✅ MongoDB connection successful")
        
        # Update the answer key
        collection = db['answer_keys']
        
        document = {
            "exam_id": "782918260130",
            "answer_key": processed_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = collection.replace_one(
            {"exam_id": "782918260130"},
            document,
            upsert=True
        )
        
        print(f"✅ MongoDB update result: upserted_id={result.upserted_id}, modified_count={result.modified_count}")
        
        # Verify the update
        retrieved = collection.find_one({"exam_id": "782918260130"})
        if retrieved and "answer_key" in retrieved:
            answer_key = retrieved["answer_key"]
            if "14" in answer_key:
                q14_retrieved = answer_key["14"]
                print(f"✅ Verification: Question 14 retrieved from MongoDB")
                print(f"  Question: {q14_retrieved.get('question', 'Not found')}")
                print(f"  Answer: {q14_retrieved.get('answer', 'Not found')[:50]}...")
                
                if "structure" in q14_retrieved:
                    structure_retrieved = q14_retrieved["structure"]
                    print(f"  Structure components: {len(structure_retrieved) if isinstance(structure_retrieved, dict) else 0}")
                    return True
                else:
                    print("  ❌ No structure found in retrieved data")
                    return False
            else:
                print("❌ Question 14 not found in retrieved data")
                return False
        else:
            print("❌ Failed to retrieve updated data")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = direct_mongodb_update()
    print(f"\nDirect MongoDB update {'SUCCESSFUL' if success else 'FAILED'}")
    
    if success:
        print("\n🎉 SUCCESS! MongoDB has been updated!")
        print("📋 What should work now:")
        print("  ✅ Expected answer field should show the correct answer")
        print("  ✅ Structure components should be displayed")
        print("  ✅ Question 14 and all other questions should work")
        print("\n🔄 Please refresh the results page to see the changes!")
    else:
        print("\n❌ Update failed. The expected answer field may still be empty.")
    
    sys.exit(0 if success else 1)
