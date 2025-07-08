"""
Answer key processing functionality.
Handles loading, processing, and saving of answer keys with embeddings and structure.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import srsly

from .config import (
    ANSWER_KEY_FILE, PROCESSED_ANSWER_KEY_FILE, ANSWER_KEY_PRODIGY_FILE,
    USE_STRUCTURE_FALLBACK
)
from .embeddings import get_mean_pooled_embedding
from .structure_analysis import infer_answer_structure, validate_structure
from .utils import validate_file_exists, print_progress
from .prodigy_formatting import process_answer_key_file

logger = logging.getLogger(__name__)


class AnswerKeyProcessor:
    """Class to handle answer key processing pipeline."""
    
    def __init__(self, data_folder: str):
        """
        Initialize the answer key processor.
        
        Args:
            data_folder: Path to the data folder containing answer key
        """
        self.data_folder = Path(data_folder)
        self.input_file = self.data_folder / ANSWER_KEY_FILE
        self.output_file = self.data_folder / PROCESSED_ANSWER_KEY_FILE
        self.prodigy_file = self.data_folder / ANSWER_KEY_PRODIGY_FILE
        
    def load_answer_key(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Load the answer key from JSON file.
        
        Returns:
            Tuple of (success, answer_key_data)
        """
        try:
            if not validate_file_exists(str(self.input_file)):
                return False, {}
            
            with open(self.input_file, "r", encoding='utf-8') as f:
                answer_key = json.load(f)
            
            logger.info(f"Loaded answer key with {len(answer_key)} questions")
            return True, answer_key
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing answer key JSON: {str(e)}")
            return False, {}
        except Exception as e:
            logger.error(f"Error loading answer key: {str(e)}")
            return False, {}
    
    def process_single_answer(
        self, 
        qno: str, 
        answer_data: Dict[str, Any], 
        use_structure_fallback: bool = USE_STRUCTURE_FALLBACK
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Process a single answer: generate embeddings and infer structure.
        
        Args:
            qno: Question number
            answer_data: Answer data dictionary
            use_structure_fallback: Whether to use simple fallback when LLM fails
            
        Returns:
            Tuple of (success, processed_answer_data)
        """
        try:
            answer_text = answer_data.get("answer", "")
            if not answer_text:
                logger.warning(f"Empty answer text for question {qno}")
                return False, answer_data
            
            processed_data = answer_data.copy()
            
            # Step 1: Generate full embedding for the answer
            logger.debug(f"Generating full embedding for question {qno}")
            full_embedding = get_mean_pooled_embedding(answer_text)
            processed_data["embedding"] = full_embedding
            
            # Step 2: Infer structure of the answer
            logger.debug(f"Inferring structure for question {qno}")
            structure = infer_answer_structure(answer_text, use_fallback=use_structure_fallback)
            processed_data["structure"] = structure
            
            # Step 3: Generate embeddings for structure components
            logger.debug(f"Generating structure component embeddings for question {qno}")
            if validate_structure(structure):
                for key in structure:
                    try:
                        content = structure[key]
                        if content is None:
                            content = ""
                        elif not isinstance(content, str):
                            content = str(content)
                        
                        content = content.strip()
                        component_embedding = get_mean_pooled_embedding(content)
                        
                        # Store both content and embedding
                        processed_data["structure"][key] = {
                            "content": content,
                            "embedding": component_embedding
                        }
                    except Exception as e:
                        logger.warning(f"Error processing structure component {qno}.{key}: {str(e)}")
                        processed_data["structure"][key] = {
                            "content": content if 'content' in locals() else "",
                            "embedding": [0.0] * 768
                        }
            
            return True, processed_data
            
        except Exception as e:
            logger.error(f"Error processing question {qno}: {str(e)}")
            
            # Store error information in answer data
            error_data = answer_data.copy()
            if "embedding" not in error_data:
                error_data["embedding"] = [0.0] * 768
            if "structure" not in error_data:
                error_data["structure"] = {"error": f"Processing failed: {str(e)}"}
            
            return False, error_data
    
    def save_processed_data(self, processed_data: Dict[str, Any]) -> bool:
        """
        Save processed answer key data to files.
        
        Args:
            processed_data: Processed answer key data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Save JSON file
            with open(self.output_file, "w", encoding='utf-8') as f:
                json.dump(processed_data, f, indent=4)
            
            # Generate and save Prodigy format
            try:
                answer_key_jsonl = process_answer_key_file(str(self.output_file))
                srsly.write_jsonl(str(self.prodigy_file), answer_key_jsonl)
                logger.info(f"Prodigy format saved to: {self.prodigy_file}")
            except Exception as e:
                logger.warning(f"Failed to generate Prodigy format: {str(e)}")
            
            logger.info(f"Processed answer key saved to: {self.output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving processed answer key: {str(e)}")
            return False
    
    def process(self, use_structure_fallback: bool = USE_STRUCTURE_FALLBACK) -> bool:
        """
        Process the complete answer key pipeline.
        
        Args:
            use_structure_fallback: Whether to use simple fallback when LLM fails
            
        Returns:
            True if successful, False otherwise
        """
        # Load answer key
        success, answer_key = self.load_answer_key()
        if not success:
            return False
        
        processed_count = 0
        error_count = 0
        total_questions = len(answer_key)
        
        print(f"Starting to process {total_questions} answers...")
        
        # Process each question
        for i, qno in enumerate(answer_key.keys(), 1):
            print(f"Processing question {qno} ({i}/{total_questions})...")
            
            success, processed_data = self.process_single_answer(
                qno, answer_key[qno], use_structure_fallback
            )
            
            answer_key[qno] = processed_data
            
            if success:
                processed_count += 1
                print(f"  ✅ Question {qno}: Successfully processed")
            else:
                error_count += 1
                print(f"  ❌ Question {qno}: Error occurred")
            
            print_progress(i, total_questions, "Progress")
            print()
        
        # Save processed data
        save_success = self.save_processed_data(answer_key)
        
        # Print summary
        print(f"\n== ANSWER KEY PROCESSING COMPLETE ==")
        print(f"Total questions: {total_questions}")
        print(f"Successfully processed: {processed_count}")
        print(f"Errors: {error_count}")
        print(f"Output saved: {'Yes' if save_success else 'No'}")
        
        return save_success and (processed_count > 0)


def process_answer_key(
    data_folder: str, 
    use_structure_fallback: bool = USE_STRUCTURE_FALLBACK
) -> bool:
    """
    Convenience function to process answer key.
    
    Args:
        data_folder: Path to data folder
        use_structure_fallback: Whether to use simple fallback when LLM fails
        
    Returns:
        True if successful, False otherwise
    """
    processor = AnswerKeyProcessor(data_folder)
    return processor.process(use_structure_fallback)
