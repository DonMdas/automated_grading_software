# Unified Database Connector Documentation

## Overview

The unified database connector provides a centralized way to manage connections to both PostgreSQL and MongoDB in your AI grading system. This allows you to leverage the strengths of both databases:

- **PostgreSQL**: For structured data like users, courses, submissions metadata, and relational data
- **MongoDB**: For unstructured data like OCR text, processed answers, grading results, and analytics

## Key Features

✅ **Config-based connections** - No hardcoded credentials  
✅ **Automatic connection management** - Handles connection pooling and cleanup  
✅ **Context managers** - Safe session handling with automatic rollback  
✅ **Error handling** - Comprehensive logging and error management  
✅ **Testing utilities** - Built-in connection testing and health checks  
✅ **Production ready** - Optimized for both development and production environments  

## Quick Start

### 1. Environment Setup

Create/update your `.env` file:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/grading_system_pg
MONGODB_URL=mongodb://localhost:27017

# Security
SECRET_KEY=your-very-secure-secret-key-here-change-in-production

# Other config...
```

### 2. Basic Usage

```python
from app.db.connector import (
    initialize_database_connections,
    get_postgres_session,
    get_mongo_collection,
    close_database_connections
)

# Initialize connections (usually done at app startup)
success = initialize_database_connections()

if success:
    # PostgreSQL usage
    with get_postgres_session() as session:
        result = session.execute(text("SELECT * FROM users"))
        users = result.fetchall()
    
    # MongoDB usage
    collection = get_mongo_collection("student_answers")
    documents = list(collection.find({"exam_id": 1}))
    
    # Cleanup (usually done at app shutdown)
    close_database_connections()
```

### 3. FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    success = initialize_database_connections()
    if not success:
        raise RuntimeError("Database initialization failed")
    
    yield  # App runs here
    
    # Shutdown
    close_database_connections()

app = FastAPI(lifespan=lifespan)
```

## Database Schema Strategy

### PostgreSQL Schema (Structured Data)

```sql
-- Users and authentication
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'teacher'
);

-- Course management
CREATE TABLE course_section (
    course_id VARCHAR(10) PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    section_id VARCHAR(5),
    teacher_id INT REFERENCES users(user_id)
);

-- Exam management
CREATE TABLE exams (
    exam_id SERIAL PRIMARY KEY,
    exam_type VARCHAR(100) NOT NULL,
    answer_key_file_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Submission metadata
CREATE TABLE submissions (
    submission_id UUID PRIMARY KEY,
    course_exam_id INT REFERENCES course_exam(course_exam_id),
    student_id VARCHAR(50) REFERENCES students(student_id),
    file_path TEXT,
    status VARCHAR(20) DEFAULT 'uploaded'
);
```

### MongoDB Collections (Unstructured Data)

```javascript
// student_answers collection
{
  "submission_id": "uuid-here",
  "student_id": "student_001", 
  "course_id": "CS101",
  "exam_id": 1,
  "processed_answers": {
    "1": "Student's answer to question 1",
    "2": "Student's answer to question 2"
  },
  "ocr_text": "Raw OCR text from the submission",
  "created_at": "2025-07-04T10:30:00Z",
  "status": "processed"
}

// answer_keys collection
{
  "exam_id": 1,
  "answer_key": {
    "1": {
      "question": "What is 2+2?",
      "answer": "4",
      "points": 10,
      "type": "numeric",
      "grading_criteria": {...}
    }
  },
  "created_at": "2025-07-04T10:00:00Z",
  "status": "active"
}

// grading_results collection
{
  "submission_id": "uuid-here",
  "results": {
    "total_score": 85,
    "max_score": 100,
    "question_scores": {...},
    "feedback": {...}
  },
  "created_at": "2025-07-04T11:00:00Z",
  "version": "2.0"
}
```

## Integration Patterns

### 1. OCR and Processing Workflow

```python
def process_submission(file_path: str, submission_id: str, exam_id: int):
    # 1. OCR processing (using your existing scripts)
    from studentanswer import extract_student_answers_to_json
    ocr_output_path = f"/tmp/{submission_id}_answers.json"
    extract_student_answers_to_json(file_path, ocr_output_path)
    
    # 2. Load processed data
    with open(ocr_output_path, 'r') as f:
        processed_answers = json.load(f)
    
    # 3. Store in MongoDB
    collection = get_mongo_collection("student_answers")
    document = {
        "submission_id": submission_id,
        "exam_id": exam_id,
        "processed_answers": processed_answers,
        "created_at": datetime.utcnow(),
        "status": "processed"
    }
    collection.insert_one(document)
    
    # 4. Update PostgreSQL status
    with get_postgres_session() as session:
        query = text("UPDATE submissions SET status = 'processed' WHERE submission_id = :id")
        session.execute(query, {"id": submission_id})
```

### 2. Grading Workflow

```python
from app.services.enhanced_grading_service import EnhancedGradingService

def grade_exam_submissions(exam_id: int):
    grading_service = EnhancedGradingService()
    
    # This will automatically:
    # 1. Get answer key from MongoDB
    # 2. Find all submissions for the exam from PostgreSQL
    # 3. Get processed answers from MongoDB
    # 4. Perform AI grading
    # 5. Store results in MongoDB
    # 6. Update submission status in PostgreSQL
    
    results = grading_service.batch_grade_submissions(exam_id)
    return results
```

### 3. Analytics and Reporting

```python
def get_course_analytics(course_id: str):
    analytics = {}
    
    # Get structured data from PostgreSQL
    with get_postgres_session() as session:
        query = text("""
            SELECT COUNT(*) as total_submissions,
                   COUNT(CASE WHEN status = 'graded' THEN 1 END) as graded
            FROM submissions s
            JOIN course_exam ce ON s.course_exam_id = ce.course_exam_id  
            WHERE ce.course_id = :course_id
        """)
        result = session.execute(query, {"course_id": course_id})
        stats = result.fetchone()
        analytics['submission_stats'] = {
            'total': stats[0],
            'graded': stats[1]
        }
    
    # Get score analytics from MongoDB
    collection = get_mongo_collection("grading_results")
    pipeline = [
        # Complex aggregation pipeline for score statistics
        {"$lookup": {...}},
        {"$match": {"course_id": course_id}},
        {"$group": {...}}
    ]
    score_stats = list(collection.aggregate(pipeline))
    analytics['score_stats'] = score_stats
    
    return analytics
```

## API Endpoints Examples

### Health Check

```python
@app.get("/health/databases")
async def check_databases():
    from app.db.connector import db_connector
    test_results = db_connector.test_connections()
    return {
        "status": "success" if all(test_results.values()) else "partial",
        "databases": test_results
    }
```

### Submission Processing

```python
@app.post("/api/submissions/{submission_id}/process")
async def process_submission(submission_id: str, file_data: UploadFile):
    # 1. Save file
    file_path = f"/uploads/{submission_id}_{file_data.filename}"
    
    # 2. OCR processing
    ocr_result = process_pdf_with_ocr(file_path)
    
    # 3. Store processed data
    collection = get_mongo_collection("student_answers")
    collection.insert_one({
        "submission_id": submission_id,
        "processed_answers": ocr_result,
        "created_at": datetime.utcnow()
    })
    
    return {"success": True, "submission_id": submission_id}
```

### Grading

```python
@app.post("/api/exams/{exam_id}/grade")
async def grade_exam(exam_id: int):
    from app.services.enhanced_grading_service import grade_all_submissions_for_exam
    
    results = grade_all_submissions_for_exam(exam_id)
    return results
```

## Error Handling and Logging

The connector includes comprehensive error handling:

```python
import logging

# Configure logging in your app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# The connector will automatically log:
# ✅ Successful connections
# ❌ Connection failures  
# 🔄 Connection retries
# 🛑 Connection cleanup
```

## Production Considerations

### 1. Connection Pooling

The connector is configured for production with:
- Connection pooling (PostgreSQL)
- Connection recycling every 5 minutes
- Pre-ping to verify connections
- Automatic retry logic

### 2. Security

- Never commit `.env` files to version control
- Use strong database passwords
- Configure PostgreSQL authentication properly
- Use SSL connections in production

### 3. Performance

- Use appropriate indexes in PostgreSQL
- Create indexes in MongoDB for common queries
- Monitor connection pool usage
- Use MongoDB aggregation pipelines for complex analytics

### 4. Monitoring

```python
# Add health checks to your app
@app.get("/health")
async def health_check():
    from app.db.connector import db_connector
    
    db_status = db_connector.test_connections()
    
    return {
        "status": "healthy" if all(db_status.values()) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "databases": db_status
    }
```

## Migration Guide

If you have existing code using direct database connections:

### Before (Direct SQLAlchemy)
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://...")
Session = sessionmaker(bind=engine)

def some_function():
    session = Session()
    try:
        result = session.query(User).all()
        session.commit()
    finally:
        session.close()
```

### After (Unified Connector)
```python
from app.db.connector import get_postgres_session
from sqlalchemy import text

def some_function():
    with get_postgres_session() as session:
        result = session.execute(text("SELECT * FROM users"))
        users = result.fetchall()
        # session.commit() and session.close() are automatic
```

## Testing

Run the connector tests:

```bash
cd /home/pratik/Desktop/ai_grading_software/backend
source venv/bin/activate
python -m app.db.connector
```

This will test both PostgreSQL and MongoDB connections and provide detailed feedback.

## Support and Troubleshooting

### Common Issues

1. **PostgreSQL connection refused**
   - Check if PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify credentials in `.env` file
   - Check PostgreSQL authentication settings

2. **MongoDB connection timeout**
   - Check if MongoDB is running: `sudo systemctl status mongod`
   - Verify MongoDB URL in `.env` file
   - Check MongoDB configuration

3. **Import errors**
   - Ensure virtual environment is activated
   - Install required dependencies: `pip install -r requirements.txt`

### Debugging

Enable debug mode by adding to your `.env`:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

This will provide detailed logging of all database operations.
