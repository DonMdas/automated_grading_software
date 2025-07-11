"""
Main pipeline for answer key and student answer processing.
"""

import os
import sys
from .config import setup_logging, DEFAULT_DATA_FOLDER
from .answer_key_processor import process_answer_key
from .student_processor import process_student_answers

# Set up logging
logger = setup_logging()

def main():
    """
    Main pipeline execution
    """
    # Default data folder - can be modified as needed
    data_folder = DEFAULT_DATA_FOLDER  # Relative to main_pipeline directory
    
    # Check for command line arguments
    use_fallback = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-fallback":
        use_fallback = False
        print("⚠️ Running without structure fallback - LLM errors will be preserved")
    
    print("=== ANSWER KEY PROCESSING PIPELINE ===")
    print(f"Data folder: {data_folder}")
    print(f"Structure fallback: {'Enabled' if use_fallback else 'Disabled'}")
    
    # Check if data folder exists
    if not os.path.exists(data_folder):
        print(f"Error: Data folder '{data_folder}' not found!")
        print("Please ensure the data folder exists and contains answer_key.json")
        return
    
    # Process answer key
    print("\n1. Processing Answer Key...")
    success = process_answer_key(data_folder, use_structure_fallback=use_fallback)
    
    if success:
        print("✅ Answer key processing completed successfully!")
        
        # Process student answers
        print("\n2. Processing Student Answers and predicting the grades...")
        success = process_student_answers(data_folder)
        
        if success:
            print("✅ Student answer processing completed successfully!")
        else:
            print("❌ Student answer processing failed!")
    else:
        print("❌ Answer key processing failed!")
        return

if __name__ == "__main__":
    main()
