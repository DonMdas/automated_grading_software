# Answer Key Processing Pipeline

A comprehensive system for processing answer keys and student submissions with automated grading using machine learning and natural language processing.

## Overview

This pipeline processes answer keys and student submissions through multiple stages:
1. **Answer Key Processing**: Generate embeddings and infer structure for answer keys
2. **Student Answer Processing**: Compare student answers with answer keys using multiple similarity metrics
3. **Grade Prediction**: Use trained models to predict grades based on similarity scores

## Architecture

The system is divided into modular components:

```
main_pipeline/
├── __init__.py                 # Package initialization
├── main.py                     # Main pipeline orchestration
├── config.py                   # Configuration and constants
├── utils.py                    # Common utility functions
├── embeddings.py               # BERT embedding functionality
├── similarity_metrics.py       # Similarity calculation functions
├── structure_analysis.py       # Structure inference and parsing
├── prediction.py               # Grade prediction functionality
├── answer_key_processor.py     # Answer key processing pipeline
├── student_processor.py        # Student answer processing pipeline
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## Features

### Answer Key Processing
- **Embedding Generation**: Creates BERT embeddings for complete answers
- **Structure Analysis**: Uses LLM to infer answer structure with fallback mechanisms
- **Component Embeddings**: Generates embeddings for individual structure components
- **Error Handling**: Robust error handling with multiple fallback strategies

### Student Answer Processing
- **Multi-metric Similarity**: Calculates cosine similarity, TF-IDF similarity, and structure similarity
- **Structure Mapping**: Maps student answer components to answer key structure
- **Grade Prediction**: Uses trained ML models to predict grades
- **Batch Processing**: Efficiently processes multiple student submissions

### Similarity Metrics
- **Cosine Similarity**: Vector-based similarity using BERT embeddings
- **TF-IDF Similarity**: Term frequency-based similarity
- **Structure Similarity**: Component-wise structure comparison

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you have the required model files:
   - Place trained grade prediction model at `Saved_models/grade_model_knn.pkl`
   - BERT model will be downloaded automatically on first run

## Usage

### Basic Usage

```python
from main_pipeline import main

# Run the complete pipeline
main()
```

### Individual Components

```python
from main_pipeline import process_answer_key, process_student_answers

# Process only answer key
success = process_answer_key("exam1", use_structure_fallback=True)

# Process only student answers (requires processed answer key)
success = process_student_answers("exam1")
```

### Custom Embedding Generation

```python
from main_pipeline import get_mean_pooled_embedding

# Generate embedding for text
embedding = get_mean_pooled_embedding("Your text here")
```

### Grade Prediction

```python
from main_pipeline import predict_grade

# Predict grade from similarity scores
grade = predict_grade(
    tfidf_score=0.85,
    full_similarity_score=0.78,
    mean_structure_similarity=0.82
)
```

## Data Structure

### Input Data Format

**Answer Key** (`answer_key.json`):
```json
{
    "Q1": {
        "question": "What is the capital of France?",
        "answer": "The capital of France is Paris..."
    },
    "Q2": {
        "question": "Explain photosynthesis.",
        "answer": "Photosynthesis is the process..."
    }
}
```

**Student Answers** (`student_answers/student_name.json`):
```json
{
    "Q1": {
        "answer": "Paris is the capital city of France..."
    },
    "Q2": {
        "answer": "Plants use sunlight to make food..."
    }
}
```

### Output Data Format

**Processed Answer Key** (`answer_key_processed.json`):
```json
{
    "Q1": {
        "question": "What is the capital of France?",
        "answer": "The capital of France is Paris...",
        "embedding": [0.1, 0.2, ...],
        "structure": {
            "component_1": {
                "content": "The capital of France is Paris",
                "embedding": [0.3, 0.4, ...]
            }
        }
    }
}
```

**Processed Student Answer** (`processed_student_answers/student_name_processed.json`):
```json
{
    "Q1": {
        "original_answer": "Paris is the capital city of France...",
        "full_similarity_score": 0.85,
        "tfidf_similarity_score": 0.78,
        "structure_similarity_scores": [0.82, 0.75],
        "mean_structure_similarity_score": 0.785,
        "total_structure_components": 2,
        "predicted_grade": "A",
        "structure": {
            "component_1": "Paris is the capital city of France"
        }
    }
}
```

## Configuration

Key configuration options in `config.py`:

- `BERT_MODEL_NAME`: BERT model to use for embeddings
- `DEFAULT_DATA_FOLDER`: Default folder for exam data
- `USE_STRUCTURE_FALLBACK`: Enable/disable structure fallback
- `MAX_STRUCTURE_COMPONENTS`: Maximum structure components to extract
- `GRADE_MODEL_PATH`: Path to trained grade prediction model

## Command Line Options

```bash
# Run with structure fallback (default)
python main.py

# Run without structure fallback
python main.py --no-fallback
```

## Error Handling

The system includes comprehensive error handling:

- **LLM Failures**: Automatic fallback to simple structure parsing
- **Embedding Errors**: Default zero embeddings for failed cases
- **File I/O Errors**: Graceful handling with informative error messages
- **JSON Parsing**: Multiple fallback strategies for malformed JSON

## Logging

The system uses Python's logging module with configurable levels:

- **INFO**: General progress information
- **WARNING**: Non-critical issues with fallback actions
- **ERROR**: Critical errors that prevent processing
- **DEBUG**: Detailed debugging information

## Performance Considerations

- **Batch Processing**: Processes multiple files efficiently
- **Memory Management**: Handles large documents with truncation
- **Model Caching**: BERT model loaded once and reused
- **Singleton Patterns**: Shared instances for embedders and predictors

## Dependencies

Core dependencies:
- `torch`: PyTorch for BERT model
- `transformers`: Hugging Face transformers library
- `scikit-learn`: Machine learning utilities
- `numpy`: Numerical computations
- `joblib`: Model serialization
- `srsly`: JSON/JSONL handling

## Troubleshooting

### Common Issues

1. **BERT Model Loading Fails**
   - Ensure internet connection for model download
   - Check available disk space
   - Verify PyTorch installation

2. **LLM Not Available**
   - System automatically falls back to simple structure parsing
   - Ensure `llm_prompting` module is available in parent directory

3. **Grade Model Not Found**
   - Place trained model at `Saved_models/grade_model_knn.pkl`
   - Check model file format and compatibility

4. **Memory Issues**
   - Reduce `MAX_SEQUENCE_LENGTH` in config
   - Process smaller batches
   - Ensure sufficient RAM (recommended: 8GB+)

## Development

### Adding New Similarity Metrics

1. Add function to `similarity_metrics.py`
2. Update processing pipeline in relevant processor
3. Modify output data structure if needed

### Extending Structure Analysis

1. Add new patterns to `simple_structure_fallback()`
2. Create new LLM prompts for specialized domains
3. Update validation in `validate_structure()`

### Custom Grade Prediction Models

1. Train model with appropriate feature format
2. Update `prediction.py` to handle new model
3. Modify feature extraction in processors

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

[Add support contact information here]
