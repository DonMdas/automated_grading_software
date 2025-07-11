# Answer Grading Pipeline - Modular Version

This is a modularized version of the answer grading pipeline that processes answer keys and student submissions for automated grading.

## Architecture

The codebase has been refactored into the following modules for better organization and maintainability:

### Core Modules

- **`config.py`** - Configuration settings, constants, and logging setup
- **`embeddings.py`** - BERT embedding generation utilities
- **`structure_analysis.py`** - Answer structure analysis and parsing
- **`similarity_metrics.py`** - Similarity calculations (cosine, TF-IDF, structure)
- **`answer_key_processor.py`** - Answer key processing pipeline
- **`student_processor.py`** - Student answer processing pipeline
- **`prediction.py`** - Grade prediction utilities
- **`utils.py`** - Common utility functions and validation
- **`main.py`** - Main pipeline orchestration

### Supporting Files

- **`prodigy_formatting.py`** - Prodigy data formatting utilities
- **`view_annotation.py`** - Annotation viewing utilities
- **`test_modules.py`** - Test script for module verification
- **`requirements.txt`** - Python dependencies
- **`__init__.py`** - Package initialization

## Usage

### Basic Usage

```bash
cd main_pipeline
python main.py
```

### With Options

```bash
# Disable structure fallback (preserve LLM errors)
python main.py --no-fallback
```

## Module Details

### embeddings.py
- `BERTEmbedder` class for BERT model management
- `get_mean_pooled_embedding()` for text embedding generation
- Singleton pattern for efficient model loading

### structure_analysis.py
- `infer_answer_structure()` - LLM-based structure inference
- `simple_structure_fallback()` - Fallback structure parsing
- `map_student_to_answer_key_structure()` - Structure mapping
- JSON parsing and error handling utilities

### similarity_metrics.py
- `calculate_cosine_similarity()` - Embedding similarity
- `calculate_tfidf_similarity()` - TF-IDF similarity
- `calculate_structure_similarity_scores()` - Structure component comparison

### answer_key_processor.py
- Complete answer key processing pipeline
- Embedding generation for full answers and structure components
- Prodigy format export

### student_processor.py
- Student answer processing and comparison
- Grade prediction integration
- Batch processing of multiple students

### prediction.py
- `GradePredictor` class for model management
- `run_prediction()` for grade prediction
- Singleton pattern for efficient model loading

### utils.py
- `load_json_file()` - Safe JSON file loading with error handling
- `save_json_file()` - Safe JSON file saving with directory creation
- `validate_answer_key_structure()` - Answer key structure validation
- `validate_student_data_structure()` - Student data validation
- `ensure_directory_exists()` - Directory creation utility

### Testing

Run the test suite to verify all modules work correctly:

```bash
python test_modules.py
```

## Data Flow

1. **Answer Key Processing** (`answer_key_processor.py`)
   - Load answer key from `exam1/answer_key.json`
   - Generate embeddings for full answers
   - Infer structure using LLM or fallback
   - Generate embeddings for structure components
   - Save to `exam1/answer_key_processed.json`

2. **Student Answer Processing** (`student_processor.py`)
   - Load processed answer key
   - Process each student submission from `exam1/student_answers/`
   - Calculate similarities and map structures
   - Predict grades using trained model
   - Save results to `exam1/processed_student_answers/`

## Configuration

Key settings can be modified in `config.py`:

- `BERT_MODEL_NAME` - BERT model to use
- `DEFAULT_DATA_FOLDER` - Default exam folder
- `LLM_MODELS` - LLM model names for different tasks
- `MAX_STRUCTURE_COMPONENTS` - Limit for structure components
- `EMBEDDING_DIMENSION` - BERT embedding size

## Error Handling

- Comprehensive logging throughout all modules
- Graceful fallbacks for LLM failures
- Validation of data structures and formats
- Error reporting with context

## Benefits of Modular Design

1. **Maintainability** - Each module has a single responsibility
2. **Testability** - Individual components can be tested in isolation
3. **Reusability** - Modules can be imported and used independently
4. **Scalability** - Easy to extend with new features
5. **Readability** - Clear separation of concerns

## Dependencies

See `requirements.txt` for the complete list of Python dependencies.

## File Structure

```
main_pipeline/
├── config.py                    # Configuration and constants
├── embeddings.py                # BERT embedding utilities
├── structure_analysis.py        # Structure analysis and parsing
├── similarity_metrics.py        # Similarity calculations
├── answer_key_processor.py      # Answer key processing
├── student_processor.py         # Student answer processing
├── prediction.py                # Grade prediction
├── utils.py                     # Common utilities and validation
├── main.py                      # Main pipeline orchestration
├── prodigy_formatting.py        # Prodigy formatting
├── view_annotation.py           # Annotation viewing
├── test_modules.py              # Module verification tests
├── requirements.txt             # Dependencies
├── __init__.py                  # Package initialization
└── README.md                    # This file
```
