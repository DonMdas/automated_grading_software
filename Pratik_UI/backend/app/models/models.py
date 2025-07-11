from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for Google OAuth users
    full_name = Column(String(255))
    role = Column(String(50), default="teacher")  # teacher, developer
    is_active = Column(Boolean, default=True)
    
    # Google OAuth fields
    google_id = Column(String(255), unique=True, nullable=True)
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Assignment(Base):
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    classroom_id = Column(String(255))  # Google Classroom ID
    max_score = Column(Float, default=100.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    teacher = relationship("User", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment")

class Submission(Base):
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    student_email = Column(String(255), nullable=False)
    student_name = Column(String(255))
    file_path = Column(String(500))
    original_filename = Column(String(255))
    ocr_text = Column(Text)
    auto_score = Column(Float)
    human_score = Column(Float)
    feedback = Column(Text)
    status = Column(String(50), default="pending")  # pending, graded, reviewed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    assignment = relationship("Assignment", back_populates="submissions")
    annotations = relationship("Annotation", back_populates="submission")

class Annotation(Base):
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    annotator_id = Column(Integer, ForeignKey("users.id"))
    x_coordinate = Column(Float)
    y_coordinate = Column(Float)
    width = Column(Float)
    height = Column(Float)
    annotation_text = Column(Text)
    annotation_type = Column(String(50))  # highlight, comment, correction
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    submission = relationship("Submission", back_populates="annotations")
    annotator = relationship("User")

class GradingCriteria(Base):
    __tablename__ = "grading_criteria"
    
    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    criterion_name = Column(String(255), nullable=False)
    max_points = Column(Float, nullable=False)
    description = Column(Text)
    keywords = Column(Text)  # JSON string of keywords to look for
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Update relationships
User.assignments = relationship("Assignment", back_populates="teacher")
