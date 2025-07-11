"""
Answer key processing module.
"""

import logging
from pathlib import Path
import srsly
from .embeddings import get_mean_pooled_embedding
from .structure_analysis import infer_answer_structure
from .prodigy_formatting import process_answer_key_file
from .config import EMBEDDING_DIMENSION
from .utils import load_json_file, save_json_file, validate_answer_key_structure
logger = logging.getLogger(__name__)

def process_answer_key(data_folder, use_structure_fallback=True):
    """
    Process answer key through the complete pipeline:
    1. Load answer key
    2. For each answer:
       - Generate full embedding
       - Infer structure
       - Generate embeddings for structure components
    3. Save processed data
    
    Args:
        data_folder: Path to data folder
        use_structure_fallback: Whether to use simple fallback when LLM fails
    
    Answer key structure expected:
    {
        qno: {
            "question": "question text",
            "answer": "answer text"
        }
    }
    """
    data_path = Path(data_folder)
    input_file = data_path / "answer_key.json"
    
    # Load answer key
    answer_key = load_json_file(input_file)
    if answer_key is None:
        return False
    
    if not validate_answer_key_structure(answer_key):
        logger.error("Answer key has invalid structure")
        return False
    
    logger.info(f"Loaded answer key with {len(answer_key)} questions")
    
    processed_count = 0
    error_count = 0
    total_questions = len(answer_key)
    
    print(f"Starting to process {total_questions} answers...")
    
    for i, qno in enumerate(answer_key.keys(), 1):
        print(f"Processing question {qno} ({i}/{total_questions})...")
        
        try:
            answer_text = answer_key[qno]["answer"]
            
            # Step 1: Generate full embedding for the answer
            print(f"  Step 1: Generating full embedding for question {qno}")
            full_embedding = get_mean_pooled_embedding(answer_text)
            answer_key[qno]["embedding"] = full_embedding
            
            # Step 2: Infer structure of the answer
            print(f"  Step 2: Inferring structure for question {qno}")
            structure_response = infer_answer_structure(answer_text, use_fallback=use_structure_fallback)
            
            # Extract breakdown and requires_llm_evaluation
            if "error" not in structure_response:
                breakdown = structure_response.get("breakdown", {})
                requires_llm_evaluation = structure_response.get("requires_llm_evaluation", [])
                
                answer_key[qno]["structure"] = breakdown
                answer_key[qno]["requires_llm_evaluation"] = requires_llm_evaluation
                
                # Step 3: Generate embeddings for structure components
                print(f"  Step 3: Generating structure component embeddings for question {qno}")
                for key in breakdown:
                    try:
                        content = breakdown[key]
                        if content is None:
                            content = ""
                        elif not isinstance(content, str):
                            content = str(content)
                        
                        content = content.strip()
                        component_embedding = get_mean_pooled_embedding(content)
                        
                        # Store both content and embedding
                        answer_key[qno]["structure"][key] = {
                            "content": content,
                            "embedding": component_embedding
                        }
                    except Exception as e:
                        logger.warning(f"Error processing structure component {qno}.{key}: {str(e)}")
                        answer_key[qno]["structure"][key] = {
                            "content": content if 'content' in locals() else "",
                            "embedding": [0.0] * EMBEDDING_DIMENSION
                        }
            else:
                # Store error information
                answer_key[qno]["structure"] = {"error": structure_response.get("error", "Unknown error")}
                answer_key[qno]["requires_llm_evaluation"] = []
            
            processed_count += 1
            print(f"  ✅ Question {qno}: Successfully processed")
            
        except Exception as e:
            logger.error(f"Error processing question {qno}: {str(e)}")
            error_count += 1
            print(f"  ❌ Question {qno}: Error - {str(e)}")
            
            # Store error information
            if "embedding" not in answer_key[qno]:
                answer_key[qno]["embedding"] = [0.0] * EMBEDDING_DIMENSION
            if "structure" not in answer_key[qno]:
                answer_key[qno]["structure"] = {"error": f"Processing failed: {str(e)}"}
            if "requires_llm_evaluation" not in answer_key[qno]:
                answer_key[qno]["requires_llm_evaluation"] = []
        
        print(f"Progress: {i}/{total_questions} processed ({processed_count} success, {error_count} errors)\n")
    
    # Save the processed answer key
    output_file = data_path / "answer_key_processed.json"
    if not save_json_file(answer_key, output_file):
        return False
    
    try:
        answer_key_jsonl = process_answer_key_file(str(data_folder) + "/answer_key_processed.json")
        srsly.write_jsonl(str(data_folder) + "/answer_key_prodigy.jsonl", answer_key_jsonl)

        print(f"\n== PROCESSING COMPLETE ==")
        print(f"Total questions: {total_questions}")
        print(f"Successfully processed: {processed_count}")
        print(f"Errors: {error_count}")
        print(f"Output saved to: {output_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing Prodigy format: {str(e)}")
        return False
