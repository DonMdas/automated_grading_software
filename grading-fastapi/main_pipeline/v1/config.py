"""
Configuration file for the answer key processing pipeline.
Contains all constants, paths, and model configurations.
"""

import logging
from pathlib import Path

# Model configurations
BERT_MODEL_NAME = "bert-base-uncased"
EMBEDDING_DIMENSION = 768
MAX_SEQUENCE_LENGTH = 512

# File paths and directories
SAVED_MODELS_DIR = "Saved_models"
GRADE_MODEL_PATH = "Saved_models/grade_model_knn.pkl"

# Processing configurations
DEFAULT_DATA_FOLDER = "exam1"
USE_STRUCTURE_FALLBACK = True
MAX_STRUCTURE_COMPONENTS = 10
MIN_COMPONENT_LENGTH = 20

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO

# LLM model names
LLM_MODELS = {
    "breakdown_model": "breakdown_model",
    "structure_mapper": "structure_mapper"
}

# File extensions and patterns
STUDENT_FILE_PATTERN = "*.json"
OUTPUT_FILE_SUFFIX = "_processed.json"
PRODIGY_FILE_SUFFIX = "_prodigy.jsonl"

# Directory names
STUDENT_ANSWERS_DIR = "student_answers"
PROCESSED_STUDENT_ANSWERS_DIR = "processed_student_answers"
PRODIGY_DATA_DIR = "prodigy_data"

# Answer key file names
ANSWER_KEY_FILE = "answer_key.json"
PROCESSED_ANSWER_KEY_FILE = "answer_key_processed.json"
ANSWER_KEY_PRODIGY_FILE = "answer_key_prodigy.jsonl"
