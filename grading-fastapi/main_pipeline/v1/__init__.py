"""
Main pipeline package for answer key processing system.

This package provides a complete pipeline for processing answer keys and student submissions,
including embedding generation, structure analysis, similarity calculations, and grade prediction.

Modules:
    - config: Configuration constants and settings
    - utils: Common utility functions
    - embeddings: BERT embedding functionality
    - similarity_metrics: Similarity calculation functions
    - structure_analysis: Structure inference and parsing
    - prediction: Grade prediction functionality
    - answer_key_processor: Answer key processing pipeline
    - student_processor: Student answer processing pipeline
    - main: Main pipeline orchestration
"""

__version__ = "1.0.0"
__author__ = "Answer Key Processing Team"

# Import main functions for easy access
from .main import main
from .answer_key_processor import process_answer_key
from .student_processor import process_student_answers
from .prediction import predict_grade, get_model_info
from .embeddings import get_mean_pooled_embedding
from .similarity_metrics import calculate_cosine_similarity, calculate_tfidf_similarity

__all__ = [
    "main",
    "process_answer_key",
    "process_student_answers",
    "predict_grade",
    "get_model_info",
    "get_mean_pooled_embedding",
    "calculate_cosine_similarity",
    "calculate_tfidf_similarity"
]
