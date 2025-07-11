"""
Student answer processing module.
"""

import logging
from pathlib import Path
import srsly
from .embeddings import get_mean_pooled_embedding
from .similarity_metrics import (
    calculate_cosine_similarity, 
    calculate_tfidf_similarity,
    calculate_structure_similarity_scores
)
from .structure_analysis import map_student_to_answer_key_structure
from .prediction import run_prediction
from .prodigy_formatting import process_student_answers_file
from .utils import load_json_file, save_json_file, validate_student_data_structure, ensure_directory_exists

logger = logging.getLogger(__name__)

def process_student_answers(data_folder):
    """
    Process student answers through the complete pipeline:
    1. Load processed answer key 
    2. Iterate through all student submissions
    3. For each student answer:
       - Generate full embedding and compare with answer key (cosine similarity)
       - Calculate TF-IDF similarity with answer key
       - Map structure components and compare embeddings
       - Calculate mean structure similarity score
    4. Save processed data without embeddings
    """
    data_path = Path(data_folder)
    answer_key_file = data_path / "answer_key_processed.json"
    student_answers_dir = data_path / "student_answers"
    output_dir = data_path / "processed_student_answers"
    prodigy_dir = data_path / "prodigy_data"
    
    # Create output directory
    ensure_directory_exists(output_dir)
    ensure_directory_exists(prodigy_dir)
    
    # Load processed answer key
    answer_key = load_json_file(answer_key_file)
    if answer_key is None:
        return False
    
    logger.info(f"Loaded processed answer key with {len(answer_key)} questions")
    
    # Check if student answers directory exists
    if not student_answers_dir.exists():
        logger.error(f"Student answers directory not found: {student_answers_dir}")
        return False
    
    # Get all student submission files
    student_files = list(student_answers_dir.glob("*.json"))
    if not student_files:
        logger.warning(f"No student submission files found in {student_answers_dir}")
        return False
    
    print(f"Found {len(student_files)} student submissions to process...")
    
    processed_students = 0
    total_students = len(student_files)
    
    for i, student_file in enumerate(student_files, 1):
        student_name = student_file.stem  # filename without extension
        print(f"Processing student {student_name} ({i}/{total_students})...")
        
        try:
            # Load student answers
            student_data = load_json_file(student_file)
            if student_data is None:
                continue
            
            if not student_data:
                logger.warning(f"Empty student file: {student_file}")
                continue
            
            processed_student_data = {}
            
            # Process each question in student submission
            for qno, student_answer_data in student_data.items():
                if qno not in answer_key:
                    logger.warning(f"Question {qno} not found in answer key for student {student_name}")
                    continue
                
                # Extract student answer text
                if isinstance(student_answer_data, dict) and "answer" in student_answer_data:
                    student_answer_text = student_answer_data["answer"]
                elif isinstance(student_answer_data, str):
                    student_answer_text = student_answer_data
                else:
                    logger.warning(f"Invalid answer format for Q{qno} in student {student_name}")
                    continue
                
                if not student_answer_text or not student_answer_text.strip():
                    logger.warning(f"Empty answer for Q{qno} in student {student_name}")
                    continue
                
                print(f"  Processing Q{qno}...")
                
                # Get answer key data
                answer_key_text = answer_key[qno]["answer"]
                answer_key_embedding = answer_key[qno]["embedding"]
                answer_key_structure = answer_key[qno]["structure"]
                requires_llm_evaluation = answer_key[qno].get("requires_llm_evaluation", [])
                
                # Step 1: Generate full embedding for student answer
                student_embedding = get_mean_pooled_embedding(student_answer_text)
                
                # Step 2: Calculate cosine similarity with answer key embedding
                full_similarity_score = calculate_cosine_similarity(student_embedding, answer_key_embedding)
                
                # Step 3: Calculate TF-IDF similarity
                tfidf_similarity_score = calculate_tfidf_similarity(student_answer_text, answer_key_text)
                
                # Step 4: Map structure and calculate structure similarity
                # Map student structure to answer key structure
                mapped_structure = map_student_to_answer_key_structure(
                    answer_key_structure, student_answer_text
                )
                
                # Calculate similarity for each structure component
                structure_similarity_scores = calculate_structure_similarity_scores(
                    answer_key_structure, mapped_structure, requires_llm_evaluation
                )
                
                # Calculate mean structure similarity
                mean_structure_similarity = (
                    sum(structure_similarity_scores) / len(structure_similarity_scores)
                    if structure_similarity_scores else 0.0
                )
                
                predicted_grade = run_prediction(
                    tfidf_similarity_score, full_similarity_score, mean_structure_similarity
                )
                
                # Store processed data (NO EMBEDDINGS)
                processed_student_data[qno] = {
                    "original_answer": student_answer_text,
                    "full_similarity_score": full_similarity_score,
                    "tfidf_similarity_score": tfidf_similarity_score,
                    "structure_similarity_scores": structure_similarity_scores,
                    "mean_structure_similarity_score": mean_structure_similarity,
                    "total_structure_components": len(answer_key_structure) if isinstance(answer_key_structure, dict) else 0,
                    "structure": mapped_structure if isinstance(mapped_structure, dict) else {"error": "Mapping failed"},
                    "predicted_grade": str(predicted_grade),
                    "requires_llm_evaluation": requires_llm_evaluation
                }
                
                print(f"    Full similarity: {full_similarity_score:.4f}")
                print(f"    TF-IDF similarity: {tfidf_similarity_score:.4f}")
                print(f"    Mean structure similarity: {mean_structure_similarity:.4f}")
                print(f"    Predicted grade: {predicted_grade}")
            
            # Save processed student data
            output_file = output_dir / f"{student_name}_processed.json"
            if not save_json_file(processed_student_data, output_file):
                logger.error(f"Failed to save data for student {student_name}")
                continue
            
            student_answer_jsonl = process_student_answers_file(output_file)
            srsly.write_jsonl(prodigy_dir / f"{student_name}_prodigy.jsonl", student_answer_jsonl)

            processed_students += 1
            print(f"  ✅ Student {student_name}: Successfully processed and saved to {output_file}")
            print(f"  ✅ Student {student_name}: Successfully processed and saved to {prodigy_dir / f'{student_name}_prodigy.jsonl'}")
        except Exception as e:
            logger.error(f"Error processing student {student_name}: {str(e)}")
            print(f"  ❌ Student {student_name}: Error - {str(e)}")
    
    print(f"\n== STUDENT PROCESSING COMPLETE ==")
    print(f"Total students: {total_students}")
    print(f"Successfully processed: {processed_students}")
    print(f"Output directory: {output_dir}")
    
    return processed_students > 0
