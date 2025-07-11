"""
Utility functions used across multiple modules.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_json_file(file_path):
    """
    Safely load a JSON file with error handling.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        dict: Loaded JSON data or None if error
    """
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON file {file_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading {file_path}: {str(e)}")
        return None

def save_json_file(data, file_path, indent=4):
    """
    Safely save data to a JSON file with error handling.
    
    Args:
        data: Data to save
        file_path: Path to save file
        indent: JSON indentation
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {str(e)}")
        return False

def validate_answer_key_structure(answer_key):
    """
    Validate that answer key has the expected structure.
    
    Args:
        answer_key: Loaded answer key data
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(answer_key, dict):
        logger.error("Answer key must be a dictionary")
        return False
    
    for qno, question_data in answer_key.items():
        if not isinstance(question_data, dict):
            logger.error(f"Question {qno} data must be a dictionary")
            return False
        
        if "answer" not in question_data:
            logger.error(f"Question {qno} missing 'answer' field")
            return False
        
        if not isinstance(question_data["answer"], str):
            logger.error(f"Question {qno} 'answer' must be a string")
            return False
    
    return True

def validate_student_data_structure(student_data):
    """
    Validate that student data has the expected structure.
    
    Args:
        student_data: Loaded student data
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(student_data, dict):
        logger.error("Student data must be a dictionary")
        return False
    
    for qno, answer_data in student_data.items():
        # Handle both string answers and dict with "answer" key
        if isinstance(answer_data, str):
            continue
        elif isinstance(answer_data, dict) and "answer" in answer_data:
            if not isinstance(answer_data["answer"], str):
                logger.error(f"Question {qno} 'answer' must be a string")
                return False
        else:
            logger.error(f"Question {qno} has invalid format")
            return False
    
    return True

def ensure_directory_exists(directory_path):
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to directory
        
    Returns:
        bool: True if directory exists/created, False otherwise
    """
    try:
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {str(e)}")
        return False
