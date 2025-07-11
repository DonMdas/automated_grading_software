#!/usr/bin/env python3
"""
Manually update MongoDB with the processed answer key for testing.
"""

import json
import sys
import os
sys.path.insert(0, '/home/don/Documents/Internship/aistudioversion')

def update_mongodb_manually():
    """Update MongoDB with the processed answer key."""
    
    print("Manually updating MongoDB with processed answer key...")
    
    processed_file = "/home/don/Documents/Internship/aistudioversion/server_data/782918260130/answer_key_processed.json"
    
    try:
        # Load the processed answer key
        with open(processed_file, 'r') as f:
            processed_data = json.load(f)
        
        print(f"✅ Loaded processed answer key with {len(processed_data)} questions")
        
        # Check if question 14 exists
        if "14" in processed_data:
            q14 = processed_data["14"]
            print(f"✅ Question 14 found:")
            print(f"  Question: {q14.get('question', 'Not found')}")
            print(f"  Answer: {q14.get('answer', 'Not found')[:100]}...")
            
            # Check structure
            structure = q14.get("structure", {})
            print(f"  Structure components: {len(structure) if isinstance(structure, dict) else 0}")
        else:
            print("❌ Question 14 not found in processed data")
            return False
        
        # Try to connect to MongoDB directly using mongosh
        import subprocess
        
        # Create a temporary JS file to insert the data
        js_script = f"""
use grading_system_mongo;
db.answer_keys.replaceOne(
    {{"exam_id": "782918260130"}},
    {{
        "exam_id": "782918260130",
        "answer_key": {json.dumps(processed_data)},
        "created_at": new Date(),
        "updated_at": new Date()
    }},
    {{"upsert": true}}
);
print("Answer key updated successfully");
"""
        
        # Write the script to a temporary file
        script_file = "/tmp/update_answer_key.js"
        with open(script_file, 'w') as f:
            f.write(js_script)
        
        print("✅ Created MongoDB update script")
        
        # Execute the script
        result = subprocess.run([
            "mongosh", "--eval", f"load('{script_file}')"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ MongoDB update successful")
            print(f"Output: {result.stdout}")
            
            # Clean up
            os.remove(script_file)
            return True
        else:
            print(f"❌ MongoDB update failed: {result.stderr}")
            return False
    
    except subprocess.TimeoutExpired:
        print("❌ MongoDB update timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval():
    """Test retrieving the answer key after update."""
    print("\nTesting answer key retrieval...")
    
    try:
        # Use mongosh to test retrieval
        import subprocess
        
        js_script = """
use grading_system_mongo;
var result = db.answer_keys.findOne({"exam_id": "782918260130"});
if (result && result.answer_key && result.answer_key["14"]) {
    print("✅ Question 14 found in MongoDB");
    print("Question:", result.answer_key["14"].question);
    print("Answer length:", result.answer_key["14"].answer.length);
    if (result.answer_key["14"].structure) {
        print("Structure components:", Object.keys(result.answer_key["14"].structure).length);
    }
} else {
    print("❌ Question 14 not found or data structure issue");
}
"""
        
        result = subprocess.run([
            "mongosh", "--eval", js_script
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print(f"MongoDB query result: {result.stdout}")
            return "✅ Question 14 found in MongoDB" in result.stdout
        else:
            print(f"❌ MongoDB query failed: {result.stderr}")
            return False
    
    except Exception as e:
        print(f"❌ Error testing retrieval: {e}")
        return False

if __name__ == "__main__":
    success1 = update_mongodb_manually()
    success2 = test_retrieval() if success1 else False
    
    overall_success = success1 and success2
    print(f"\nUpdate {'SUCCESSFUL' if overall_success else 'FAILED'}")
    
    if overall_success:
        print("\n🚀 MongoDB has been updated with processed answer key!")
        print("The API should now return proper expected answers and structure components.")
    else:
        print("\n❌ MongoDB update failed. The API may still show empty expected answers.")
    
    sys.exit(0 if overall_success else 1)
