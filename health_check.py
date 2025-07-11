#!/usr/bin/env python3
"""
Project Health Check - Verify that all core components are working after cleanup.
"""

import sys
import traceback
from pathlib import Path

def check_imports():
    """Check if all required modules can be imported."""
    print("🔍 Checking imports...")
    
    try:
        import main
        print("✓ Main module imported successfully")
        
        import config
        print("✓ Config module imported successfully")
        
        import database
        print("✓ Database module imported successfully")
        
        import auth
        print("✓ Auth module imported successfully")
        
        import background_tasks
        print("✓ Background tasks module imported successfully")
        
        import grading_wrapper
        print("✓ Grading wrapper module imported successfully")
        
        from api import auth as api_auth
        print("✓ API auth module imported successfully")
        
        from api import classroom
        print("✓ API classroom module imported successfully")
        
        from api import submissions
        print("✓ API submissions module imported successfully")
        
        from api import evaluation
        print("✓ API evaluation module imported successfully")
        
        from api import results
        print("✓ API results module imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def check_file_structure():
    """Check if all required files and directories exist."""
    print("\n🔍 Checking file structure...")
    
    required_files = [
        "main.py",
        "config.py", 
        "database.py",
        "auth.py",
        "background_tasks.py",
        "grading_wrapper.py",
        "requirements.txt",
        "README.md",
        "api/__init__.py",
        "api/auth.py",
        "api/classroom.py",
        "api/submissions.py",
        "api/evaluation.py",
        "api/results.py",
        "static/css/app.css",
        "static/js/api.js",
        "static/js/auth.js",
        "static/js/evaluation.js",
        "templates/index.html",
        "templates/dashboard.html",
        "templates/evaluation.html"
    ]
    
    required_dirs = [
        "api",
        "static",
        "static/css",
        "static/js", 
        "templates",
        "services",
        "ocr_code",
        "grading-fastapi",
        "training_data"
    ]
    
    missing_files = []
    missing_dirs = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
        else:
            print(f"✓ {dir_path}/")
    
    if missing_files:
        print(f"\n✗ Missing files: {missing_files}")
        return False
        
    if missing_dirs:
        print(f"\n✗ Missing directories: {missing_dirs}")
        return False
    
    return True

def check_grading_engines():
    """Check if grading engines are available."""
    print("\n🔍 Checking grading engines...")
    
    try:
        from grading_wrapper import GradingPipelineWrapper
        
        # Test v2 engine
        wrapper_v2 = GradingPipelineWrapper('test_folder', 'v2')
        if wrapper_v2.initialize_processors():
            print("✓ Grading engine v2 initialized successfully")
        else:
            print("✗ Grading engine v2 initialization failed")
            
        # Test v1 engine
        wrapper_v1 = GradingPipelineWrapper('test_folder', 'v1')
        if wrapper_v1.initialize_processors():
            print("✓ Grading engine v1 initialized successfully")
        else:
            print("✗ Grading engine v1 initialization failed")
            
        return True
        
    except Exception as e:
        print(f"✗ Grading engine check failed: {e}")
        traceback.print_exc()
        return False

def main():
    print("🚀 AI Studio Project Health Check")
    print("=" * 50)
    
    all_good = True
    
    # Check imports
    if not check_imports():
        all_good = False
    
    # Check file structure
    if not check_file_structure():
        all_good = False
    
    # Check grading engines
    if not check_grading_engines():
        all_good = False
    
    print("\n" + "=" * 50)
    if all_good:
        print("🎉 All checks passed! Project is ready to run.")
        print("\nTo start the application:")
        print("  uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    else:
        print("❌ Some checks failed. Please review the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
