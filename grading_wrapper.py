"""
Wrapper module to handle grading pipeline integration.
This module provides a simple interface to the grading pipeline
without exposing the complex internal structure.
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from typing import Tuple, Optional

# Add the grading-fastapi path to handle imports
grading_fastapi_path = Path(__file__).parent / "grading-fastapi"
sys.path.insert(0, str(grading_fastapi_path))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GradingPipelineWrapper:
    """
    A wrapper class to handle the grading pipeline integration.
    This class provides a simple interface to run the grading process.
    """
    
    def __init__(self, data_folder: str, version: str = "v2"):
        """
        Initialize the grading pipeline wrapper.
        
        Args:
            data_folder: Path to the data folder containing exam data
            version: Version of the grading pipeline to use ("v1" or "v2")
        """
        self.data_folder = Path(data_folder)
        self.version = version
        self.answer_key_processor = None
        self.student_processor = None
        
    def initialize_processors(self) -> bool:
        """
        Initialize the answer key and student processors.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Change to the grading-fastapi directory to handle relative imports
            original_cwd = os.getcwd()
            os.chdir(grading_fastapi_path)
            
            if self.version == "v1":
                from main_pipeline.v1.answer_key_processor import process_answer_key
                from main_pipeline.v1.student_processor import process_student_answers
            elif self.version == "v2":
                from main_pipeline.v2.answer_key_processor import process_answer_key
                from main_pipeline.v2.student_processor import process_student_answers
            else:
                raise ValueError(f"Invalid version: {self.version}")
            
            self.process_answer_key = process_answer_key
            self.process_student_answers = process_student_answers
            
            # Change back to original directory
            os.chdir(original_cwd)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize processors: {e}")
            # Change back to original directory even on error
            try:
                os.chdir(original_cwd)
            except:
                pass
            return False
    
    def run_grading_pipeline(self) -> Tuple[bool, str]:
        """
        Run the complete grading pipeline.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Initialize processors
            if not self.initialize_processors():
                return False, "Failed to initialize grading processors"
            
            # Get absolute path to the original data folder
            original_data_folder = os.path.abspath(self.data_folder)
            
            # Check if required files exist in the original location
            answer_key_file = Path(original_data_folder) / "answer_key.json"
            student_answers_dir = Path(original_data_folder) / "student_answers"
            student_ocr_dir = Path(original_data_folder) / "student_submissions_ocr"
            
            if not answer_key_file.exists():
                return False, f"Answer key file not found: {answer_key_file}"
            
            # Check for student answers or OCR files
            if not student_answers_dir.exists():
                if student_ocr_dir.exists() and any(student_ocr_dir.glob("*.json")):
                    # Create student_answers directory and copy OCR files
                    student_answers_dir.mkdir(exist_ok=True)
                    for ocr_file in student_ocr_dir.glob("*.json"):
                        shutil.copy2(ocr_file, student_answers_dir / ocr_file.name)
                    logger.info(f"Copied {len(list(student_ocr_dir.glob('*.json')))} OCR files to student_answers directory")
                else:
                    return False, f"No student answer files found in: {student_answers_dir} or {student_ocr_dir}"
            elif not any(student_answers_dir.glob("*.json")):
                return False, f"No student answer files found in: {student_answers_dir}"
            
            # Change to the grading-fastapi directory to handle relative imports
            original_cwd = os.getcwd()
            grading_fastapi_path = Path(__file__).parent / "grading-fastapi"
            os.chdir(grading_fastapi_path)
            
            # Extract the coursework_id from the path (last part of the path)
            coursework_id = Path(original_data_folder).name
            
            # Create the expected directory structure within grading-fastapi
            grading_server_data_dir = Path("server_data")
            grading_coursework_dir = grading_server_data_dir / coursework_id
            grading_coursework_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy required files to the grading-fastapi directory structure
            logger.info(f"Setting up grading environment for coursework {coursework_id}")
            
            # Copy answer key
            dest_answer_key = grading_coursework_dir / "answer_key.json"
            shutil.copy2(answer_key_file, dest_answer_key)
            logger.info(f"Copied answer key to: {dest_answer_key}")
            
            # Copy student answers
            dest_student_answers = grading_coursework_dir / "student_answers"
            if dest_student_answers.exists():
                shutil.rmtree(dest_student_answers)
            shutil.copytree(student_answers_dir, dest_student_answers)
            logger.info(f"Copied student answers to: {dest_student_answers}")
            
            try:
                # Process answer key with relative path (now it exists in grading-fastapi/server_data)
                logger.info("Processing answer key...")
                success_ak = self.process_answer_key(f"server_data/{coursework_id}")
                if not success_ak:
                    return False, "Failed to process answer key"
                
                # Process student answers with relative path
                logger.info("Processing student answers...")
                success_sa = self.process_student_answers(f"server_data/{coursework_id}")
                if not success_sa:
                    return False, "Failed to process student answers"
                
                # Copy results back to original location
                grading_prodigy_dir = grading_coursework_dir / "prodigy_data"
                original_prodigy_dir = Path(original_data_folder) / "prodigy_data"
                
                if grading_prodigy_dir.exists():
                    if original_prodigy_dir.exists():
                        shutil.rmtree(original_prodigy_dir)
                    shutil.copytree(grading_prodigy_dir, original_prodigy_dir)
                    logger.info(f"Copied results back to: {original_prodigy_dir}")
                
                # Copy answer key prodigy file back to original location
                answer_key_prodigy_file = grading_coursework_dir / "answer_key_prodigy.jsonl"
                original_answer_key_prodigy = Path(original_data_folder) / "answer_key_prodigy.jsonl"
                
                if answer_key_prodigy_file.exists():
                    shutil.copy2(answer_key_prodigy_file, original_answer_key_prodigy)
                    logger.info(f"Copied answer key prodigy file back to: {original_answer_key_prodigy}")
                else:
                    logger.warning("Answer key prodigy file not found in grading directory")
                
                # Copy processed answer key file back to original location
                answer_key_processed_file = grading_coursework_dir / "answer_key_processed.json"
                original_answer_key_processed = Path(original_data_folder) / "answer_key_processed.json"
                
                if answer_key_processed_file.exists():
                    shutil.copy2(answer_key_processed_file, original_answer_key_processed)
                    logger.info(f"Copied processed answer key file back to: {original_answer_key_processed}")
                else:
                    logger.warning("Processed answer key file not found in grading directory")
                
                # Count the number of result files
                result_files = list(original_prodigy_dir.glob("*_prodigy.jsonl"))
                if not result_files:
                    return False, "No result files generated"
                
                # Clean up temporary files
                try:
                    shutil.rmtree(grading_server_data_dir)
                    logger.info("Cleaned up temporary grading files")
                except:
                    pass  # Don't fail if cleanup fails
                
                return True, f"Grading completed successfully. Generated {len(result_files)} result files."
                
            finally:
                # Change back to original directory
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error(f"Grading pipeline failed: {e}")
            return False, f"Grading pipeline failed: {str(e)}"

def run_grading_pipeline(data_folder: str, version: str = "v2") -> Tuple[bool, str]:
    """
    Convenience function to run the grading pipeline.
    
    Args:
        data_folder: Path to the data folder containing exam data
        version: Version of the grading pipeline to use ("v1" or "v2")
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    wrapper = GradingPipelineWrapper(data_folder, version)
    return wrapper.run_grading_pipeline()

# Test function
def test_grading_pipeline():
    """Test the grading pipeline with sample data."""
    
    # Find a sample data directory
    base_dir = Path(__file__).parent
    server_data_dir = base_dir / "server_data"
    
    if not server_data_dir.exists():
        print("No server_data directory found for testing")
        return False
    
    # Find the first subdirectory with required files
    for subdir in server_data_dir.iterdir():
        if subdir.is_dir():
            answer_key_file = subdir / "answer_key.json"
            student_answers_dir = subdir / "student_answers"
            student_ocr_dir = subdir / "student_submissions_ocr"
            
            # Check if we have either student_answers or student_submissions_ocr
            has_data = (answer_key_file.exists() and 
                       ((student_answers_dir.exists() and any(student_answers_dir.glob("*.json"))) or
                        (student_ocr_dir.exists() and any(student_ocr_dir.glob("*.json")))))
            
            if has_data:
                print(f"Testing with data from: {subdir}")
                success, message = run_grading_pipeline(str(subdir))
                print(f"Result: {message}")
                return success
    
    print("No suitable test data found")
    return False

if __name__ == "__main__":
    test_grading_pipeline()
