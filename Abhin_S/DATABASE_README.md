# AI Grading Platform - Database Documentation

> **Note**: This is a simplified schema for the application. The full-fledged schema is as shown in the ER diagram.

## 📋 Overview

The AI Grading Platform uses a **hybrid database architecture** combining PostgreSQL for structured relational data and MongoDB for document-based storage. This approach optimizes data storage and retrieval based on the specific requirements of different data types.

## 🏗️ Database Architecture

### Hybrid Database Design
- **PostgreSQL**: Handles structured, relational data with ACID compliance
- **MongoDB**: Manages semi-structured documents like OCR results and grading data
- **Cross-database transactions**: Coordinated through the service layer

### Database Selection Rationale
- **PostgreSQL**: User management, course relationships, authentication sessions
- **MongoDB**: OCR results, AI-generated content, flexible JSON documents, training data

## 📊 Database Schema

### PostgreSQL Tables

#### Core Entity Tables
1. **`users`** - User account management
   - UUID primary keys for security
   - Google OAuth integration
   - Role-based access control

2. **`user_sessions`** - Authentication session management
   - Secure session tracking
   - Automatic expiration handling

3. **`courses`** - Google Classroom integration
   - Course metadata and relationships
   - Teacher-course associations

4. **`assignments`** - Course assignment management
   - Google Classroom assignment sync
   - Assignment metadata

5. **`students`** - Student enrollment tracking
   - Course-student relationships
   - Google Classroom roster sync

6. **`exams`** - Exam definition and management
   - Exam metadata and configuration
   - Answer key associations

7. **`submissions`** - Student submission tracking
   - Submission metadata
   - Grading status tracking

8. **`grading_tasks`** - Asynchronous grading queue
   - Background task management
   - Processing status tracking

### MongoDB Collections

#### Document Storage Collections
1. **`answer_keys`** - Answer key documents
   - Structured answer data
   - OCR processing results
   - Question-answer mappings

2. **`student_answers`** - OCR extracted answers
   - Raw OCR output
   - Processed answer data
   - Image annotations

3. **`grading_results`** - AI grading output
   - Automated grading scores
   - Confidence metrics
   - Detailed feedback

4. **`grade_edits`** - Manual grade modifications
   - Teacher adjustments
   - Edit history tracking
   - Audit trail

5. **`training_data`** - Machine learning datasets
   - Model training samples
   - Feature extraction data
   - Performance metrics

## 🔧 Database Configuration

### Environment Variables
```bash
# PostgreSQL Configuration
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=postgres123
POSTGRES_DATABASE=grading_system_pg
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# MongoDB Configuration
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=grading_system_mongo
```

### Connection Strings
- **PostgreSQL**: `postgresql://postgres:postgres123@localhost:5432/grading_system_pg`
- **MongoDB**: `mongodb://localhost:27017`

## 📁 File Structure

### Core Database Files
```
├── database.py              # Core database models and setup (347 lines)
├── config.py                # Database configuration (88 lines)
├── init_db.py               # Database initialization script (105 lines)
├── db_service.py            # High-level database operations (349 lines)
├── db_adapter.py            # Legacy compatibility layer (121 lines)
└── config_v2.py             # Alternative configuration (84 lines)
```

### Key Components

#### `database.py` - Core Models
- SQLAlchemy ORM models for PostgreSQL
- MongoDB collection definitions
- Database connection management
- Cross-database utility functions

#### `init_db.py` - Initialization Script
- Database setup and verification
- Table and collection creation
- Connection testing utilities
- Automated schema deployment

#### `db_service.py` - Service Layer
- High-level business logic operations
- CRUD operations for all entities
- Cross-database transaction coordination
- Data validation and processing

#### `config.py` - Configuration Management
- Environment variable handling
- Connection string generation
- Security settings
- Application parameters

## 🚀 Database Initialization

### Automated Setup
```bash
# Run the initialization script
python init_db.py
```

### Manual Setup
```python
from database import initialize_databases
initialize_databases()
```

### What Gets Created
- **PostgreSQL Tables**: All entity tables with proper relationships
- **MongoDB Collections**: Document collections with performance indexes
- **Indexes**: Optimized query performance indexes
- **Constraints**: Data integrity constraints

## 🔍 Database Operations

### PostgreSQL Operations
```python
from db_service import DatabaseService

# Initialize service
db_service = DatabaseService()

# User operations
user = db_service.create_user(email="user@example.com", full_name="John Doe")
users = db_service.get_users_by_role("teacher")

# Course operations
course = db_service.create_course(google_course_id="123", name="Math 101")
courses = db_service.get_courses_by_teacher(teacher_id)

# Submission operations
submission = db_service.create_submission(student_id, assignment_id, data)
submissions = db_service.get_submissions_by_assignment(assignment_id)
```

### MongoDB Operations
```python
from database import MongoCollections

# Get collections
answer_keys = MongoCollections.get_collection(MongoCollections.ANSWER_KEYS)
student_answers = MongoCollections.get_collection(MongoCollections.STUDENT_ANSWERS)

# Document operations
answer_key_doc = {
    "exam_id": "exam_123",
    "questions": [...],
    "answers": [...],
    "created_at": datetime.utcnow()
}
answer_keys.insert_one(answer_key_doc)

# Query operations
results = student_answers.find({"submission_id": "sub_123"})
```

## 🔐 Security Features

### PostgreSQL Security
- **UUID Primary Keys**: Enhanced security over sequential IDs
- **SQL Injection Protection**: SQLAlchemy ORM parameterized queries
- **Connection Pooling**: Secure connection management
- **Role-based Access**: User role enforcement

### MongoDB Security
- **Index Optimization**: Performance and security indexes
- **Document Validation**: Schema validation at application level
- **Connection Security**: Secure connection strings
- **Access Control**: Collection-level access management

## 📈 Performance Optimizations

### PostgreSQL Indexes
- Primary key indexes on all UUID fields
- Foreign key indexes for relationship queries
- Composite indexes for common query patterns
- Unique constraints for data integrity

### MongoDB Indexes
```python
# Performance indexes created automatically
mongodb_db[MongoCollections.ANSWER_KEYS].create_index("exam_id", unique=True)
mongodb_db[MongoCollections.STUDENT_ANSWERS].create_index("submission_id", unique=True)
mongodb_db[MongoCollections.GRADING_RESULTS].create_index("submission_id", unique=True)
mongodb_db[MongoCollections.GRADE_EDITS].create_index("submission_id")
mongodb_db[MongoCollections.TRAINING_DATA].create_index("created_at")
```

## 🔄 Data Flow

### Typical Operations Flow
1. **User Authentication**: PostgreSQL user sessions
2. **Course Sync**: Google Classroom → PostgreSQL courses/students
3. **Assignment Creation**: PostgreSQL assignment records
4. **Answer Key Upload**: OCR processing → MongoDB answer_keys
5. **Student Submissions**: File upload → PostgreSQL + MongoDB storage
6. **OCR Processing**: Images → MongoDB student_answers
7. **AI Grading**: Processing → MongoDB grading_results
8. **Grade Review**: Teacher edits → MongoDB grade_edits
9. **Final Grades**: Aggregation → PostgreSQL grade fields

## 🛠️ Maintenance Operations

### Database Backup
```bash
# PostgreSQL backup
pg_dump grading_system_pg > backup_postgres.sql

# MongoDB backup
mongodump --db grading_system_mongo --out backup_mongo/
```

### Database Migration
```python
# Schema updates
from database import Base, engine
Base.metadata.create_all(bind=engine)

# Data migration utilities available in db_adapter.py
```

### Performance Monitoring
```python
# Connection monitoring
from database import engine, mongodb_client

# PostgreSQL connection pool status
print(engine.pool.status())

# MongoDB connection status
print(mongodb_client.admin.command('ismaster'))
```

## 🧪 Testing

### Database Testing
```python
# Test database connections
python init_db.py

# Test specific operations
from db_service import DatabaseService
db_service = DatabaseService()
# Run test operations...
```

### Connection Verification
- PostgreSQL connection testing with retry logic
- MongoDB connection validation
- Cross-database transaction testing
- Performance benchmarking utilities

## 📝 Notes for Development

### Best Practices
- Use the service layer (`db_service.py`) for all database operations
- Implement proper error handling for both database types
- Use transactions for data consistency across databases
- Follow the established naming conventions for collections/tables

### Legacy Compatibility
- `db_adapter.py` provides backward compatibility
- Gradual migration from old schema supported
- Legacy API endpoints maintained during transition

### Environment Setup
- Ensure both PostgreSQL and MongoDB are running
- Configure environment variables properly
- Use the initialization script for new deployments
- Monitor connection pool settings for production use

---

This hybrid database architecture provides the flexibility to handle both structured educational data and dynamic AI-generated content efficiently, while maintaining data integrity and performance across the entire AI grading platform.
