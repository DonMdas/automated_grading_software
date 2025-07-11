"""
Similarity metrics for comparing text embeddings and content.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

def calculate_cosine_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings"""
    try:
        if not embedding1 or not embedding2:
            return 0.0
        
        # Convert to numpy arrays and reshape
        emb1 = np.array(embedding1).reshape(1, -1)
        emb2 = np.array(embedding2).reshape(1, -1)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(emb1, emb2)[0][0]
        return float(similarity)
    except Exception as e:
        logger.warning(f"Error calculating cosine similarity: {str(e)}")
        return 0.0

def calculate_tfidf_similarity(text1, text2):
    """Calculate TF-IDF cosine similarity between two texts"""
    try:
        if not text1.strip() or not text2.strip():
            return 0.0
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return float(similarity)
    except Exception as e:
        logger.warning(f"Error calculating TF-IDF similarity: {str(e)}")
        return 0.0

def calculate_structure_similarity_scores(answer_key_structure, mapped_structure, requires_llm_evaluation):
    """
    Calculate similarity scores for structure components.
    
    Args:
        answer_key_structure: Dictionary of answer key structure components
        mapped_structure: Dictionary of mapped student structure components  
        requires_llm_evaluation: List of components requiring LLM evaluation
        
    Returns:
        List of similarity scores for each component
    """
    from .embeddings import get_mean_pooled_embedding
    import sys
    import os
    
    # Add parent directory to path to import modules
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from .llm_prompting import invoke_llm
    from .config import LLM_MODELS
    
    structure_similarity_scores = []
    
    for ak_key, ak_data in answer_key_structure.items():
        if isinstance(ak_data, dict) and "embedding" in ak_data:
            if ak_key in mapped_structure:
                # Check if this component requires LLM evaluation
                if ak_key in requires_llm_evaluation:
                    # Use LLM evaluation for this component
                    try:
                        evaluation_result = invoke_llm(
                            LLM_MODELS["special_case_evaluation"], 
                            mapped_structure[ak_key]
                        )
                        
                        # Extract integer part and divide by 10
                        import re
                        numbers = re.findall(r'\d+', evaluation_result)
                        if numbers:
                            score = int(numbers[0]) / 10.0
                            # Ensure score is between 0 and 1
                            score = max(0.0, min(1.0, score))
                        else:
                            score = 0.0
                    except (ValueError, IndexError, Exception):
                        score = 0.0
                    
                    structure_similarity_scores.append(score)
                else:
                    # Use cosine similarity for this component
                    student_component_embedding = get_mean_pooled_embedding(mapped_structure[ak_key])
                    component_similarity = calculate_cosine_similarity(
                        student_component_embedding, ak_data["embedding"]
                    )
                    structure_similarity_scores.append(component_similarity)
            else:
                # No mapping found, score as 0
                structure_similarity_scores.append(0.0)
    
    return structure_similarity_scores
