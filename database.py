"""
Database models and configuration for the AI Studio application.
Hybrid approach using PostgreSQL for relational data and MongoDB for JSON documents.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, sessionmaker, declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

from config import SQLALCHEMY_DATABASE_URL, DATABASE_CONNECT_ARGS, MONGODB_URL, MONGODB_DATABASE

# PostgreSQL Database Setup
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=DATABASE_CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MongoDB Database Setup
mongodb_client = MongoClient(MONGODB_URL)
mongodb_db = mongodb_client[MONGODB_DATABASE]

class MongoCollections:
    """MongoDB collection names and references"""
    # OCR Results
    ANSWER_KEYS = "answer_keys"
    STUDENT_ANSWERS = "student_answers"
    
    # Grading Results
    GRADING_RESULTS = "grading_results"
    GRADE_EDITS = "grade_edits"
    
    # Training Data
    TRAINING_DATA = "training_data"
    
    @classmethod
    def get_collection(cls, name: str) -> Collection:
        """Get MongoDB collection by name"""
        return mongodb_db[name]

# PostgreSQL Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="teacher")
    google_credentials = Column(Text)  # JSON string of Google credentials
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="teacher", cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    google_course_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    section = Column(String)
    description = Column(Text)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    teacher = relationship("User", back_populates="courses")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="course", cascade="all, delete-orphan")

class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    google_assignment_id = Column(String, unique=True, index=True, nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")
    exams = relationship("Exam", back_populates="assignment", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    google_student_id = Column(String, index=True, nullable=False)  # Removed unique=True
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Create a unique constraint on the combination of google_student_id and course_id
    # This allows the same student to be in multiple courses
    __table_args__ = (
        UniqueConstraint('google_student_id', 'course_id', name='unique_student_per_course'),
    )
    
    # Relationships
    course = relationship("Course", back_populates="students")
    submissions = relationship("Submission", back_populates="student", cascade="all, delete-orphan")

class Exam(Base):
    __tablename__ = "exams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False)
    title = Column(String, nullable=False)
    answer_key_id = Column(String)  # MongoDB document ID
    status = Column(String, default="CREATED")  # CREATED, ACTIVE, COMPLETED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    assignment = relationship("Assignment", back_populates="exams")
    submissions = relationship("Submission", back_populates="exam", cascade="all, delete-orphan")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    google_submission_id = Column(String, unique=True, index=True, nullable=False)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    google_drive_id = Column(String)
    local_file_path = Column(String)
    student_answers_id = Column(String)  # MongoDB document ID
    grading_results_id = Column(String)  # MongoDB document ID
    status = Column(String, default="PENDING")  # PENDING, DOWNLOADED, OCR_COMPLETE, OCR_FAILED, GRaded, GRADING_FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exam = relationship("Exam", back_populates="submissions")
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")

class GradingTask(Base):
    __tablename__ = "grading_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    task_id = Column(String, unique=True, index=True, nullable=False)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id"), nullable=False)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=True)
    grading_version = Column(String, default="v2")  # v1 or v2
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    progress = Column(Integer, default=0)
    message = Column(String)
    result_summary = Column(Text)  # JSON string of results summary
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    assignment = relationship("Assignment")
    exam = relationship("Exam")

# MongoDB Helper Functions
class MongoDBManager:
    """MongoDB database manager for handling JSON documents"""
    
    def __init__(self):
        self.db = mongodb_db
    
    def store_answer_key(self, exam_id: str, answer_key_data: Dict[str, Any]) -> str:
        """Store answer key in MongoDB (replace if exists)"""
        document = {
            "exam_id": exam_id,
            "answer_key": answer_key_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Use replace_one with upsert=True to handle duplicates
        result = self.db[MongoCollections.ANSWER_KEYS].replace_one(
            {"exam_id": exam_id}, 
            document, 
            upsert=True
        )
        
        # Return the object ID (either inserted or updated)
        if result.upserted_id:
            return str(result.upserted_id)
        else:
            # If it was an update, find the document to get its ID
            existing_doc = self.db[MongoCollections.ANSWER_KEYS].find_one({"exam_id": exam_id})
            return str(existing_doc["_id"]) if existing_doc else None
    
    def get_answer_key(self, exam_id: str) -> Optional[Dict[str, Any]]:
        """Get answer key from MongoDB"""
        document = self.db[MongoCollections.ANSWER_KEYS].find_one({"exam_id": exam_id})
        return document.get("answer_key") if document else None
    
    def store_student_answers(self, submission_id: str, student_answers: Dict[str, Any]) -> str:
        """Store student answers in MongoDB (replace if exists)"""
        document = {
            "submission_id": submission_id,
            "student_answers": student_answers,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Use replace_one with upsert=True to handle duplicates
        result = self.db[MongoCollections.STUDENT_ANSWERS].replace_one(
            {"submission_id": submission_id}, 
            document, 
            upsert=True
        )
        
        # Return the object ID (either inserted or updated)
        if result.upserted_id:
            return str(result.upserted_id)
        else:
            # If it was an update, find the document to get its ID
            existing_doc = self.db[MongoCollections.STUDENT_ANSWERS].find_one({"submission_id": submission_id})
            return str(existing_doc["_id"]) if existing_doc else None
    
    def get_student_answers(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get student answers from MongoDB"""
        document = self.db[MongoCollections.STUDENT_ANSWERS].find_one({"submission_id": submission_id})
        return document.get("student_answers") if document else None
    
    def store_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> str:
        """Store grading results in MongoDB (replace if exists)"""
        document = {
            "submission_id": submission_id,
            "grading_results": grading_results,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Use replace_one with upsert=True to handle duplicates
        result = self.db[MongoCollections.GRADING_RESULTS].replace_one(
            {"submission_id": submission_id}, 
            document, 
            upsert=True
        )
        
        # Return the object ID (either inserted or updated)
        if result.upserted_id:
            return str(result.upserted_id)
        else:
            # If it was an update, find the document to get its ID
            existing_doc = self.db[MongoCollections.GRADING_RESULTS].find_one({"submission_id": submission_id})
            return str(existing_doc["_id"]) if existing_doc else None
    
    def get_grading_results(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get grading results from MongoDB"""
        document = self.db[MongoCollections.GRADING_RESULTS].find_one({"submission_id": submission_id})
        return document.get("grading_results") if document else None
    
    def update_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> bool:
        """Update grading results in MongoDB"""
        result = self.db[MongoCollections.GRADING_RESULTS].update_one(
            {"submission_id": submission_id},
            {
                "$set": {
                    "grading_results": grading_results,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    def store_grade_edit(self, edit_data: Dict[str, Any]) -> str:
        """Store grade edit in MongoDB"""
        edit_data["created_at"] = datetime.utcnow()
        result = self.db[MongoCollections.GRADE_EDITS].insert_one(edit_data)
        return str(result.inserted_id)
    
    def store_training_data(self, training_data: Dict[str, Any]) -> str:
        """Store training data in MongoDB"""
        training_data["created_at"] = datetime.utcnow()
        result = self.db[MongoCollections.TRAINING_DATA].insert_one(training_data)
        return str(result.inserted_id)

# Global MongoDB manager instance
mongo_manager = MongoDBManager()

def get_db():
    """Dependency to get PostgreSQL database session."""
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

def get_mongo_db():
    """Dependency to get MongoDB database"""
    return mongo_manager

def create_tables():
    """Create all PostgreSQL database tables."""
    Base.metadata.create_all(bind=engine)

def init_mongodb():
    """Initialize MongoDB collections with indexes"""
    # Create indexes for better performance
    mongodb_db[MongoCollections.ANSWER_KEYS].create_index("exam_id", unique=True)
    mongodb_db[MongoCollections.STUDENT_ANSWERS].create_index("submission_id", unique=True)
    mongodb_db[MongoCollections.GRADING_RESULTS].create_index("submission_id", unique=True)
    mongodb_db[MongoCollections.GRADE_EDITS].create_index("submission_id")
    mongodb_db[MongoCollections.TRAINING_DATA].create_index("created_at")

def initialize_databases():
    """Initialize both PostgreSQL and MongoDB databases"""
    print("Initializing PostgreSQL database...")
    create_tables()
    print("PostgreSQL tables created successfully!")
    
    print("Initializing MongoDB database...")
    init_mongodb()
    print("MongoDB collections and indexes created successfully!")

# Helper function to generate formatted course IDs
def generate_course_id(google_course_id: str) -> str:
    """Generate formatted course ID from Google course ID"""
    return f"COURSE_{google_course_id}"

# Helper function to generate formatted assignment IDs
def generate_assignment_id(google_assignment_id: str) -> str:
    """Generate formatted assignment ID from Google assignment ID"""
    return f"ASSIGN_{google_assignment_id}"
