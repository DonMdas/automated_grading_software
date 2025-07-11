# AI Grading Platform - Database Schema Documentation

> **Note**: This document contains the complete database schema for the AI Grading Platform, including PostgreSQL table structures and MongoDB document schemas.

## 📊 PostgreSQL Database Schema

### Database Information
- **Database Name**: `grading_system_pg`
- **Engine**: PostgreSQL
- **ORM**: SQLAlchemy
- **Primary Key Type**: UUID (for enhanced security)
- **Character Set**: UTF-8

---

## 📋 PostgreSQL Tables

### 1. `users` - User Account Management

```sql
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             VARCHAR UNIQUE NOT NULL,
    full_name         VARCHAR NOT NULL,
    role              VARCHAR DEFAULT 'teacher',
    google_credentials TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT users_email_key UNIQUE (email),
    INDEX idx_users_email (email),
    INDEX idx_users_id (id)
);
```

**Description**: Stores user account information with Google OAuth integration.

**Fields**:
- `id`: UUID primary key
- `email`: User's email address (unique)
- `full_name`: User's display name
- `role`: User role ('teacher', 'admin', etc.)
- `google_credentials`: JSON string of Google OAuth credentials
- `created_at`: Account creation timestamp
- `updated_at`: Last modification timestamp

---

### 2. `user_sessions` - Authentication Session Management

```sql
CREATE TABLE user_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  VARCHAR UNIQUE NOT NULL,
    user_id     UUID NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT user_sessions_session_id_key UNIQUE (session_id),
    CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_sessions_session_id (session_id),
    INDEX idx_user_sessions_user_id (user_id)
);
```

**Description**: Manages user authentication sessions with automatic expiration.

**Fields**:
- `id`: UUID primary key
- `session_id`: Unique session identifier
- `user_id`: Reference to users table
- `expires_at`: Session expiration timestamp
- `created_at`: Session creation timestamp

---

### 3. `courses` - Google Classroom Integration

```sql
CREATE TABLE courses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_course_id VARCHAR UNIQUE NOT NULL,
    name             VARCHAR NOT NULL,
    section          VARCHAR,
    description      TEXT,
    teacher_id       UUID NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT courses_google_course_id_key UNIQUE (google_course_id),
    CONSTRAINT courses_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_courses_google_course_id (google_course_id),
    INDEX idx_courses_teacher_id (teacher_id)
);
```

**Description**: Stores Google Classroom course information synchronized from Google APIs.

**Fields**:
- `id`: UUID primary key
- `google_course_id`: Google Classroom course ID (unique)
- `name`: Course name
- `section`: Course section/class
- `description`: Course description
- `teacher_id`: Reference to course teacher
- `created_at`: Course creation timestamp
- `updated_at`: Last modification timestamp

---

### 4. `assignments` - Course Assignment Management

```sql
CREATE TABLE assignments (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_assignment_id VARCHAR UNIQUE NOT NULL,
    course_id            UUID NOT NULL,
    title                VARCHAR NOT NULL,
    description          TEXT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT assignments_google_assignment_id_key UNIQUE (google_assignment_id),
    CONSTRAINT assignments_course_id_fkey FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    INDEX idx_assignments_google_assignment_id (google_assignment_id),
    INDEX idx_assignments_course_id (course_id)
);
```

**Description**: Manages course assignments synchronized from Google Classroom.

**Fields**:
- `id`: UUID primary key
- `google_assignment_id`: Google Classroom assignment ID (unique)
- `course_id`: Reference to courses table
- `title`: Assignment title
- `description`: Assignment description
- `created_at`: Assignment creation timestamp
- `updated_at`: Last modification timestamp

---

### 5. `students` - Student Enrollment Tracking

```sql
CREATE TABLE students (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_student_id VARCHAR NOT NULL,
    course_id         UUID NOT NULL,
    name              VARCHAR NOT NULL,
    email             VARCHAR,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_student_per_course UNIQUE (google_student_id, course_id),
    CONSTRAINT students_course_id_fkey FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    INDEX idx_students_google_student_id (google_student_id),
    INDEX idx_students_course_id (course_id)
);
```

**Description**: Tracks student enrollments in courses (allows same student in multiple courses).

**Fields**:
- `id`: UUID primary key
- `google_student_id`: Google student identifier
- `course_id`: Reference to courses table
- `name`: Student name
- `email`: Student email address
- `created_at`: Enrollment timestamp

**Note**: Composite unique constraint allows same student in multiple courses.

---

### 6. `exams` - Exam Definition and Management

```sql
CREATE TABLE exams (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id  UUID NOT NULL,
    title          VARCHAR NOT NULL,
    answer_key_id  VARCHAR,  -- MongoDB document ID
    status         VARCHAR DEFAULT 'CREATED',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT exams_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    INDEX idx_exams_assignment_id (assignment_id),
    INDEX idx_exams_status (status)
);
```

**Description**: Defines exams within assignments with answer key references.

**Fields**:
- `id`: UUID primary key
- `assignment_id`: Reference to assignments table
- `title`: Exam title
- `answer_key_id`: MongoDB document ID for answer key
- `status`: Exam status ('CREATED', 'ACTIVE', 'COMPLETED')
- `created_at`: Exam creation timestamp
- `updated_at`: Last modification timestamp

---

### 7. `submissions` - Student Submission Tracking

```sql
CREATE TABLE submissions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_submission_id  VARCHAR UNIQUE NOT NULL,
    exam_id               UUID NOT NULL,
    assignment_id         UUID NOT NULL,
    student_id            UUID NOT NULL,
    google_drive_id       VARCHAR,
    local_file_path       VARCHAR,
    student_answers_id    VARCHAR,  -- MongoDB document ID
    grading_results_id    VARCHAR,  -- MongoDB document ID
    status                VARCHAR DEFAULT 'PENDING',
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT submissions_google_submission_id_key UNIQUE (google_submission_id),
    CONSTRAINT submissions_exam_id_fkey FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    CONSTRAINT submissions_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    CONSTRAINT submissions_student_id_fkey FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_submissions_google_submission_id (google_submission_id),
    INDEX idx_submissions_exam_id (exam_id),
    INDEX idx_submissions_assignment_id (assignment_id),
    INDEX idx_submissions_student_id (student_id),
    INDEX idx_submissions_status (status)
);
```

**Description**: Tracks student submissions with references to MongoDB documents for OCR data and grading results.

**Fields**:
- `id`: UUID primary key
- `google_submission_id`: Google Classroom submission ID (unique)
- `exam_id`: Reference to exams table
- `assignment_id`: Reference to assignments table
- `student_id`: Reference to students table
- `google_drive_id`: Google Drive file ID
- `local_file_path`: Local file storage path
- `student_answers_id`: MongoDB document ID for OCR results
- `grading_results_id`: MongoDB document ID for grading results
- `status`: Processing status ('PENDING', 'DOWNLOADED', 'OCR_COMPLETE', 'OCR_FAILED', 'GRADED', 'GRADING_FAILED')
- `created_at`: Submission creation timestamp
- `updated_at`: Last modification timestamp

---

### 8. `grading_tasks` - Asynchronous Grading Queue

```sql
CREATE TABLE grading_tasks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id          VARCHAR UNIQUE NOT NULL,
    assignment_id    UUID NOT NULL,
    exam_id          UUID,
    grading_version  VARCHAR DEFAULT 'v2',
    status           VARCHAR DEFAULT 'PENDING',
    progress         INTEGER DEFAULT 0,
    message          VARCHAR,
    result_summary   TEXT,  -- JSON string
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at     TIMESTAMP,
    
    CONSTRAINT grading_tasks_task_id_key UNIQUE (task_id),
    CONSTRAINT grading_tasks_assignment_id_fkey FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    CONSTRAINT grading_tasks_exam_id_fkey FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE SET NULL,
    INDEX idx_grading_tasks_task_id (task_id),
    INDEX idx_grading_tasks_assignment_id (assignment_id),
    INDEX idx_grading_tasks_status (status)
);
```

**Description**: Manages background grading tasks with progress tracking.

**Fields**:
- `id`: UUID primary key
- `task_id`: Unique task identifier
- `assignment_id`: Reference to assignments table
- `exam_id`: Optional reference to exams table
- `grading_version`: Grading engine version ('v1', 'v2')
- `status`: Task status ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')
- `progress`: Task completion percentage (0-100)
- `message`: Status message
- `result_summary`: JSON string of task results
- `created_at`: Task creation timestamp
- `completed_at`: Task completion timestamp

---

## 🗄️ MongoDB Database Schema

### Database Information
- **Database Name**: `grading_system_mongo`
- **Engine**: MongoDB
- **Document Format**: JSON/BSON
- **Indexing**: Performance-optimized indexes

---

## 📄 MongoDB Collections

### 1. `answer_keys` - Answer Key Documents

```json
{
  "_id": ObjectId("..."),
  "exam_id": "string",
  "answer_key": {
    "metadata": {
      "exam_title": "string",
      "total_questions": "number",
      "total_marks": "number",
      "created_by": "string",
      "version": "string"
    },
    "questions": [
      {
        "question_number": "number",
        "question_type": "string",  // "mcq", "short_answer", "essay", "numerical"
        "question_text": "string",
        "correct_answer": "string|array",
        "marks": "number",
        "partial_marks": {
          "enabled": "boolean",
          "criteria": "array"
        },
        "keywords": ["string"],
        "acceptable_variations": ["string"]
      }
    ],
    "grading_rubric": {
      "overall_criteria": "string",
      "grade_thresholds": {
        "A": "number",
        "B": "number",
        "C": "number",
        "D": "number"
      }
    }
  },
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

**Indexes**:
- `exam_id` (unique)
- `created_at`

---

### 2. `student_answers` - OCR Extracted Answers

```json
{
  "_id": ObjectId("..."),
  "submission_id": "string",
  "student_answers": {
    "metadata": {
      "student_name": "string",
      "submission_time": "ISODate",
      "file_info": {
        "filename": "string",
        "file_size": "number",
        "mime_type": "string",
        "page_count": "number"
      },
      "ocr_info": {
        "engine": "string",
        "confidence": "number",
        "processing_time": "number",
        "version": "string"
      }
    },
    "extracted_answers": [
      {
        "question_number": "number",
        "raw_text": "string",
        "processed_text": "string",
        "confidence_score": "number",
        "bounding_box": {
          "x": "number",
          "y": "number",
          "width": "number",
          "height": "number"
        },
        "page_number": "number",
        "annotations": {
          "handwriting_quality": "string",
          "text_clarity": "string",
          "potential_issues": ["string"]
        }
      }
    ],
    "quality_metrics": {
      "overall_confidence": "number",
      "readability_score": "number",
      "completeness": "number",
      "issues_detected": ["string"]
    }
  },
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

**Indexes**:
- `submission_id` (unique)
- `created_at`
- `student_answers.metadata.student_name`

---

### 3. `grading_results` - AI Grading Output

```json
{
  "_id": ObjectId("..."),
  "submission_id": "string",
  "grading_results": {
    "metadata": {
      "grading_engine": "string",
      "version": "string",
      "graded_at": "ISODate",
      "processing_time": "number",
      "total_score": "number",
      "max_score": "number",
      "percentage": "number",
      "grade": "string"
    },
    "question_results": [
      {
        "question_number": "number",
        "student_answer": "string",
        "correct_answer": "string",
        "score_awarded": "number",
        "max_score": "number",
        "percentage": "number",
        "is_correct": "boolean",
        "confidence": "number",
        "ai_analysis": {
          "similarity_score": "number",
          "keyword_match": "array",
          "semantic_similarity": "number",
          "grammar_check": "object",
          "reasoning": "string"
        },
        "feedback": {
          "positive_points": ["string"],
          "areas_for_improvement": ["string"],
          "suggestions": ["string"],
          "detailed_explanation": "string"
        },
        "partial_credit": {
          "applied": "boolean",
          "criteria_met": ["string"],
          "justification": "string"
        }
      }
    ],
    "overall_feedback": {
      "strengths": ["string"],
      "weaknesses": ["string"],
      "recommendations": ["string"],
      "overall_comment": "string"
    },
    "quality_indicators": {
      "confidence_level": "string",
      "reliability_score": "number",
      "flags": ["string"],
      "requires_manual_review": "boolean"
    }
  },
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

**Indexes**:
- `submission_id` (unique)
- `grading_results.metadata.graded_at`
- `grading_results.metadata.total_score`

---

### 4. `grade_edits` - Manual Grade Modifications

```json
{
  "_id": ObjectId("..."),
  "submission_id": "string",
  "editor_id": "string",
  "edit_type": "string",  // "score_change", "feedback_update", "full_regrade"
  "changes": {
    "question_number": "number",
    "field_changed": "string",  // "score", "feedback", "status"
    "old_value": "any",
    "new_value": "any",
    "reason": "string",
    "notes": "string"
  },
  "before_edit": {
    "total_score": "number",
    "question_scores": "array",
    "grade": "string"
  },
  "after_edit": {
    "total_score": "number",
    "question_scores": "array",
    "grade": "string"
  },
  "audit_info": {
    "editor_name": "string",
    "editor_role": "string",
    "ip_address": "string",
    "user_agent": "string",
    "session_id": "string"
  },
  "created_at": "ISODate"
}
```

**Indexes**:
- `submission_id`
- `editor_id`
- `created_at`
- `edit_type`

---

### 5. `training_data` - Machine Learning Datasets

```json
{
  "_id": ObjectId("..."),
  "dataset_type": "string",  // "ocr_training", "grading_training", "feedback_training"
  "source_submission_id": "string",
  "training_sample": {
    "input_data": {
      "question_text": "string",
      "student_answer": "string",
      "correct_answer": "string",
      "context": "object"
    },
    "expected_output": {
      "score": "number",
      "feedback": "string",
      "classification": "string"
    },
    "features": {
      "text_similarity": "number",
      "keyword_density": "number",
      "semantic_features": "array",
      "linguistic_features": "object"
    }
  },
  "validation_data": {
    "human_verified": "boolean",
    "verifier_id": "string",
    "verification_date": "ISODate",
    "quality_score": "number",
    "notes": "string"
  },
  "usage_metadata": {
    "model_version": "string",
    "training_epoch": "number",
    "performance_impact": "number",
    "last_used": "ISODate"
  },
  "created_at": "ISODate"
}
```

**Indexes**:
- `dataset_type`
- `source_submission_id`
- `created_at`
- `training_sample.expected_output.score`
- `validation_data.human_verified`

---

## 🔗 Relationships and References

### Cross-Database References
- PostgreSQL `exams.answer_key_id` → MongoDB `answer_keys._id`
- PostgreSQL `submissions.student_answers_id` → MongoDB `student_answers._id`
- PostgreSQL `submissions.grading_results_id` → MongoDB `grading_results._id`

### PostgreSQL Foreign Key Relationships
```
users (1) ←→ (N) user_sessions
users (1) ←→ (N) courses
courses (1) ←→ (N) assignments
courses (1) ←→ (N) students
assignments (1) ←→ (N) exams
assignments (1) ←→ (N) submissions
assignments (1) ←→ (N) grading_tasks
exams (1) ←→ (N) submissions
students (1) ←→ (N) submissions
```

### MongoDB Document Relationships
```
answer_keys.exam_id → exams.id (PostgreSQL)
student_answers.submission_id → submissions.id (PostgreSQL)
grading_results.submission_id → submissions.id (PostgreSQL)
grade_edits.submission_id → submissions.id (PostgreSQL)
training_data.source_submission_id → submissions.id (PostgreSQL)
```

---

## 📊 Data Types and Constraints

### PostgreSQL Data Types
- **UUID**: Primary keys and foreign keys
- **VARCHAR**: Text fields with reasonable limits
- **TEXT**: Large text content (descriptions, JSON)
- **TIMESTAMP**: Date/time with timezone support
- **INTEGER**: Numeric values (progress, scores)

### MongoDB Data Types
- **ObjectId**: MongoDB document identifiers
- **String**: Text data
- **Number**: Numeric values (scores, metrics)
- **Array**: Lists of items
- **Object**: Nested documents
- **ISODate**: Timestamp fields
- **Boolean**: True/false values

### Unique Constraints
- All Google-sourced IDs must be unique
- Email addresses must be unique
- Session IDs must be unique
- Task IDs must be unique
- Composite constraints for student-course relationships

This schema supports the full AI grading workflow from user authentication through final grade delivery, with proper data separation between structured relational data and flexible document storage.
