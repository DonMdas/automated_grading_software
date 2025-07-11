"""
Student answer processing functionality.
Handles processing of student submissions, similarity calculations, and grade prediction.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
import srsly

from config import (
    PROCESSED_ANSWER_KEY_FILE, STUDENT_ANSWERS_DIR, PROCESSED_STUDENT_ANSWERS_DIR,
    PRODIGY_DATA_DIR, STUDENT_FILE_PATTERN, OUTPUT_FILE_SUFFIX, PRODIGY_FILE_SUFFIX
)
from embeddings import get_mean_pooled_embedding
from similarity_metrics import (
    calculate_cosine_similarity, calculate_tfidf_similarity, 
    calculate_structure_similarities, calculate_mean_similarity
)
from structure_analysis import infer_answer_structure, map_student_to_answer_key_structure
from prediction import predict_grade
from utils import validate_file_exists, ensure_directory_exists, print_progress
from prodigy_formatting import process_student_answers_file

logger = logging.getLogger(__name__)


class StudentAnswerProcessor:
    """Class to handle student answer processing pipeline."""
    
    def __init__(self, data_folder: str):
        """
        Initialize the student answer processor.
        
        Args:
            data_folder: Path to the data folder
        """
        self.data_folder = Path(data_folder)
        self.answer_key_file = self.data_folder / PROCESSED_ANSWER_KEY_FILE
        self.student_answers_dir = self.data_folder / STUDENT_ANSWERS_DIR
        self.output_dir = self.data_folder / PROCESSED_STUDENT_ANSWERS_DIR
        self.prodigy_dir = self.data_folder / PRODIGY_DATA_DIR
        
        # Create output directories
        ensure_directory_exists(str(self.output_dir))
        ensure_directory_exists(str(self.prodigy_dir))
    
    def load_answer_key(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Load the processed answer key.
        
        Returns:
            Tuple of (success, answer_key_data)
        """
        try:
            if not validate_file_exists(str(self.answer_key_file)):
                return False, {}
            
            with open(self.answer_key_file, "r", encoding='utf-8') as f:
                answer_key = json.load(f)
            
            logger.info(f"Loaded processed answer key with {len(answer_key)} questions")
            return True, answer_key
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing answer key JSON: {str(e)}")
            return False, {}
        except Exception as e:
            logger.error(f"Error loading answer key: {str(e)}")
            return False, {}
    
    def get_student_files(self) -> List[Path]:
        """
        Get list of student submission files.
        
        Returns:
            List of student file paths
        """
        if not self.student_answers_dir.exists():
            logger.error(f"Student answers directory not found: {self.student_answers_dir}")
            return []
        
        student_files = list(self.student_answers_dir.glob(STUDENT_FILE_PATTERN))
        if not student_files:
            logger.warning(f"No student submission files found in {self.student_answers_dir}")
        
        return student_files
    
    def load_student_data(self, student_file: Path) -> Tuple[bool, Dict[str, Any]]:
        """
        Load student answer data from file.
        
        Args:
            student_file: Path to student submission file
            
        Returns:
            Tuple of (success, student_data)
        """
        try:
            with open(student_file, "r", encoding='utf-8') as f:
                student_data = json.load(f)
            
            if not student_data:
                logger.warning(f"Empty student file: {student_file}")
                return False, {}
            
            return True, student_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing student JSON {student_file}: {str(e)}")
            return False, {}
        except Exception as e:
            logger.error(f"Error loading student file {student_file}: {str(e)}")
            return False, {}
    
    def process_single_student_answer(
        self,
        qno: str,
        student_answer_data: Any,
        answer_key_data: Dict[str, Any],
        student_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a single student answer for one question.
        
        Args:
            qno: Question number
            student_answer_data: Student answer data
            answer_key_data: Corresponding answer key data
            student_name: Name of the student
            
        Returns:
            Tuple of (success, processed_data)
        """
        try:
            # Extract student answer text
            if isinstance(student_answer_data, dict) and "answer" in student_answer_data:
                student_answer_text = student_answer_data["answer"]
            elif isinstance(student_answer_data, str):
                student_answer_text = student_answer_data
            else:
                logger.warning(f"Invalid answer format for Q{qno} in student {student_name}")
                return False, {}
            
            if not student_answer_text or not student_answer_text.strip():
                logger.warning(f"Empty answer for Q{qno} in student {student_name}")
                return False, {}
            
            # Get answer key data
            answer_key_text = answer_key_data.get("answer", "")
            answer_key_embedding = answer_key_data.get("embedding", [])
            answer_key_structure = answer_key_data.get("structure", {})
            
            # Step 1: Generate full embedding for student answer
            student_embedding = get_mean_pooled_embedding(student_answer_text)
            
            # Step 2: Calculate cosine similarity with answer key embedding
            full_similarity_score = calculate_cosine_similarity(student_embedding, answer_key_embedding)
            
            # Step 3: Calculate TF-IDF similarity
            tfidf_similarity_score = calculate_tfidf_similarity(student_answer_text, answer_key_text)
            
            # Step 4: Process structure and calculate structure similarity
            student_structure = infer_answer_structure(student_answer_text, use_fallback=True)
            structure_similarity_scores = []
            mapped_structure = {}
            
            if isinstance(student_structure, dict) and "error" not in student_structure:
                # Map student structure to answer key structure
                mapped_structure = map_student_to_answer_key_structure(
                    student_structure, answer_key_structure, student_answer_text
                )
                
                # Calculate similarity for each structure component
                structure_similarity_scores = calculate_structure_similarities(
                    mapped_structure, answer_key_structure, get_mean_pooled_embedding
                )
            
            # Calculate mean structure similarity
            mean_structure_similarity = calculate_mean_similarity(structure_similarity_scores)
            
            # Step 5: Predict grade
            predicted_grade = predict_grade(
                tfidf_similarity_score, full_similarity_score, mean_structure_similarity
            )
            
            # Prepare processed data (NO EMBEDDINGS stored)
            processed_data = {
                "original_answer": student_answer_text,
                "full_similarity_score": full_similarity_score,
                "tfidf_similarity_score": tfidf_similarity_score,
                "structure_similarity_scores": structure_similarity_scores,
                "mean_structure_similarity_score": mean_structure_similarity,
                "total_structure_components": len(answer_key_structure) if isinstance(answer_key_structure, dict) else 0,
                "structure": mapped_structure,
                "predicted_grade": str(predicted_grade)
            }
            
            logger.debug(f"Q{qno} - Full: {full_similarity_score:.4f}, "
                        f"TF-IDF: {tfidf_similarity_score:.4f}, "
                        f"Structure: {mean_structure_similarity:.4f}, "
                        f"Grade: {predicted_grade}")
            
            return True, processed_data
            
        except Exception as e:
            logger.error(f"Error processing Q{qno} for student {student_name}: {str(e)}")
            return False, {}
    
    def process_single_student(
        self,
        student_file: Path,
        answer_key: Dict[str, Any]
    ) -> bool:
        """
        Process all answers for a single student.
        
        Args:
            student_file: Path to student submission file
            answer_key: Answer key data
            
        Returns:
            True if successful, False otherwise
        """
        student_name = student_file.stem
        
        try:
            # Load student data
            success, student_data = self.load_student_data(student_file)
            if not success:
                return False
            
            processed_student_data = {}
            
            # Process each question
            for qno, student_answer_data in student_data.items():
                if qno not in answer_key:
                    logger.warning(f"Question {qno} not found in answer key for student {student_name}")
                    continue
                
                print(f"  Processing Q{qno}...")
                
                success, processed_data = self.process_single_student_answer(
                    qno, student_answer_data, answer_key[qno], student_name
                )
                
                if success:
                    processed_student_data[qno] = processed_data
                    
                    # Print metrics
                    print(f"    Full similarity: {processed_data['full_similarity_score']:.4f}")
                    print(f"    TF-IDF similarity: {processed_data['tfidf_similarity_score']:.4f}")
                    print(f"    Mean structure similarity: {processed_data['mean_structure_similarity_score']:.4f}")
                    print(f"    Predicted grade: {processed_data['predicted_grade']}")
            
            # Save processed student data
            output_file = self.output_dir / f"{student_name}{OUTPUT_FILE_SUFFIX}"
            with open(output_file, "w", encoding='utf-8') as f:
                json.dump(processed_student_data, f, indent=4)
            
            # Generate Prodigy format
            try:
                student_answer_jsonl = process_student_answers_file(output_file)
                prodigy_file = self.prodigy_dir / f"{student_name}{PRODIGY_FILE_SUFFIX}"
                srsly.write_jsonl(str(prodigy_file), student_answer_jsonl)
                print(f"  ✅ Prodigy format saved to: {prodigy_file}")
            except Exception as e:
                logger.warning(f"Failed to generate Prodigy format for {student_name}: {str(e)}")
            
            print(f"  ✅ Student {student_name}: Successfully processed and saved to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing student {student_name}: {str(e)}")
            print(f"  ❌ Student {student_name}: Error - {str(e)}")
            return False
    
    def process(self) -> bool:
        """
        Process all student submissions.
        
        Returns:
            True if at least one student was processed successfully
        """
        # Load processed answer key
        success, answer_key = self.load_answer_key()
        if not success:
            return False
        
        # Get student files
        student_files = self.get_student_files()
        if not student_files:
            return False
        
        processed_students = 0
        total_students = len(student_files)
        
        print(f"Found {total_students} student submissions to process...")
        
        # Process each student
        for i, student_file in enumerate(student_files, 1):
            student_name = student_file.stem
            print(f"Processing student {student_name} ({i}/{total_students})...")
            
            success = self.process_single_student(student_file, answer_key)
            
            if success:
                processed_students += 1
            
            print_progress(i, total_students, "Progress")
            print()
        
        # Print summary
        print(f"\n== STUDENT PROCESSING COMPLETE ==")
        print(f"Total students: {total_students}")
        print(f"Successfully processed: {processed_students}")
        print(f"Output directory: {self.output_dir}")
        print(f"Prodigy directory: {self.prodigy_dir}")
        
        return processed_students > 0


def process_student_answers(data_folder: str) -> bool:
    """
    Convenience function to process student answers.
    
    Args:
        data_folder: Path to data folder
        
    Returns:
        True if successful, False otherwise
    """
    processor = StudentAnswerProcessor(data_folder)
    return processor.process()
