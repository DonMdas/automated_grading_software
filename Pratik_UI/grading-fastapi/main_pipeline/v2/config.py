"""
Configuration settings and constants for the answer grading pipeline.
"""

import logging
import os
from pathlib import Path

# Logging configuration
def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

# Model paths and configurations
BERT_MODEL_NAME = "bert-base-uncased"
EMBEDDING_DIMENSION = 768
MAX_SEQUENCE_LENGTH = 512

# File paths
SAVED_MODELS_DIR = "Saved_models"
GRADE_MODEL_PATH = os.path.join(SAVED_MODELS_DIR, "grade_model_knn.pkl")

# Default data folder
DEFAULT_DATA_FOLDER = "exam1"

# Processing configuration
MAX_STRUCTURE_COMPONENTS = 10
MIN_CONTENT_LENGTH = 20

# LLM models for different tasks
LLM_MODELS = {
    "breakdown_model": "breakdown_model",
    "structure_mapper": "structure_mapper", 
    "special_case_evaluation": "special_case_evaluation"
}
