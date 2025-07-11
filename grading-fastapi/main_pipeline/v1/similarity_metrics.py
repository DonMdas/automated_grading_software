"""
Similarity calculation functions for comparing embeddings and texts.
Includes cosine similarity and TF-IDF similarity calculations.
"""

import numpy as np
import logging
from typing import List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def calculate_cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
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


def calculate_tfidf_similarity(text1: str, text2: str) -> float:
    """
    Calculate TF-IDF cosine similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        TF-IDF cosine similarity score between 0 and 1
    """
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


def calculate_structure_similarities(
    student_structure: dict, 
    answer_key_structure: dict,
    embedder_func
) -> List[float]:
    """
    Calculate similarity scores for structure components.
    
    Args:
        student_structure: Student answer structure components
        answer_key_structure: Answer key structure components
        embedder_func: Function to generate embeddings
        
    Returns:
        List of similarity scores for each component
    """
    similarity_scores = []
    
    for ak_key, ak_data in answer_key_structure.items():
        if isinstance(ak_data, dict) and "embedding" in ak_data:
            if ak_key in student_structure:
                # Generate embedding for student component
                student_component_embedding = embedder_func(student_structure[ak_key])
                component_similarity = calculate_cosine_similarity(
                    student_component_embedding, ak_data["embedding"]
                )
                similarity_scores.append(component_similarity)
            else:
                # No mapping found, score as 0
                similarity_scores.append(0.0)
    
    return similarity_scores


def calculate_mean_similarity(scores: List[float]) -> float:
    """
    Calculate mean similarity from a list of scores.
    
    Args:
        scores: List of similarity scores
        
    Returns:
        Mean similarity score, 0.0 if list is empty
    """
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def calculate_weighted_similarity(
    scores: List[float], 
    weights: List[float] = None
) -> float:
    """
    Calculate weighted similarity from a list of scores.
    
    Args:
        scores: List of similarity scores
        weights: List of weights for each score (defaults to equal weights)
        
    Returns:
        Weighted similarity score
    """
    if not scores:
        return 0.0
    
    if weights is None:
        weights = [1.0] * len(scores)
    
    if len(scores) != len(weights):
        logger.warning("Scores and weights length mismatch, using equal weights")
        weights = [1.0] * len(scores)
    
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    
    weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
    return weighted_sum / total_weight
