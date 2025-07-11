#!/usr/bin/env python3
"""
Integration Example: How to use the Unified Database Connector in your FastAPI application

This demonstrates how to integrate the connector with your grading system workflow.
"""

import sys
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
import json

# Add the backend directory to the path
sys.path.insert(0, '/home/pratik/Desktop/ai_grading_software/backend')

from app.db.connector import (
    initialize_database_connections, 
    get_postgres_session, 
    get_mongo_collection,
    close_database_connections
)
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GradingSystemDatabase:
    """
    Example class showing how to use the unified connector for grading system operations
    """
    
    def __init__(self):
        self.initialized = False
    
    def initialize(self) -> bool:
        """Initialize database connections"""
        self.initialized = initialize_database_connections()
        return self.initialized
    
    def store_student_submission(self, student_id: str, course_id: str, exam_id: int, 
                               submission_data: Dict[str, Any]) -> bool:
        """
        Example: Store a student submission in PostgreSQL and processed answers in MongoDB
        """
        if not self.initialized:
            logger.error("Database not initialized")
            return False
        
        try:
            # Store metadata in PostgreSQL
            with get_postgres_session() as session:
                # Insert into submissions table
                query = text("""
                    INSERT INTO submissions (submission_id, course_exam_id, student_id, file_path, status)
                    VALUES (:submission_id, (
                        SELECT course_exam_id FROM course_exam 
                        WHERE course_id = :course_id AND exam_id = :exam_id
                    ), :student_id, :file_path, 'uploaded')
                    RETURNING submission_id
                """)
                
                result = session.execute(query, {
                    'submission_id': submission_data['submission_id'],
                    'course_id': course_id,
                    'exam_id': exam_id,
                    'student_id': student_id,
                    'file_path': submission_data['file_path']
                })
                
                submission_id = result.fetchone()[0]
                logger.info(f"✅ Stored submission metadata in PostgreSQL: {submission_id}")
            
            # Store OCR processed data in MongoDB
            mongo_collection = get_mongo_collection("student_answers")
            document = {
                "submission_id": submission_data['submission_id'],
                "student_id": student_id,
                "course_id": course_id,
                "exam_id": exam_id,
                "processed_answers": submission_data.get('processed_answers', {}),
                "ocr_text": submission_data.get('ocr_text', ''),
                "created_at": datetime.utcnow(),
                "status": "processed"
            }
            
            result = mongo_collection.insert_one(document)
            logger.info(f"✅ Stored processed answers in MongoDB: {result.inserted_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing submission: {e}")
            return False
    
    def store_answer_key(self, exam_id: int, answer_key_data: Dict[str, Any]) -> bool:
        """
        Example: Store answer key in MongoDB
        """
        if not self.initialized:
            logger.error("Database not initialized")
            return False
        
        try:
            mongo_collection = get_mongo_collection("answer_keys")
            document = {
                "exam_id": exam_id,
                "answer_key": answer_key_data,
                "created_at": datetime.utcnow(),
                "status": "active"
            }
            
            result = mongo_collection.insert_one(document)
            logger.info(f"✅ Stored answer key in MongoDB: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing answer key: {e}")
            return False
    
    def get_submissions_for_grading(self, exam_id: int) -> List[Dict[str, Any]]:
        """
        Example: Get submissions that need grading
        """
        if not self.initialized:
            logger.error("Database not initialized")
            return []
        
        try:
            submissions = []
            
            # Get submission metadata from PostgreSQL
            with get_postgres_session() as session:
                query = text("""
                    SELECT s.submission_id, s.student_id, s.file_path, s.status
                    FROM submissions s
                    JOIN course_exam ce ON s.course_exam_id = ce.course_exam_id
                    WHERE ce.exam_id = :exam_id AND s.status = 'uploaded'
                """)
                
                result = session.execute(query, {'exam_id': exam_id})
                pg_submissions = result.fetchall()
            
            # Get processed answers from MongoDB
            mongo_collection = get_mongo_collection("student_answers")
            
            for submission in pg_submissions:
                submission_id = submission[0]
                mongo_doc = mongo_collection.find_one({"submission_id": submission_id})
                
                if mongo_doc:
                    submissions.append({
                        "submission_id": submission_id,
                        "student_id": submission[1],
                        "file_path": submission[2],
                        "status": submission[3],
                        "processed_answers": mongo_doc.get("processed_answers", {}),
                        "ocr_text": mongo_doc.get("ocr_text", "")
                    })
            
            logger.info(f"✅ Retrieved {len(submissions)} submissions for grading")
            return submissions
            
        except Exception as e:
            logger.error(f"❌ Error getting submissions: {e}")
            return []
    
    def store_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> bool:
        """
        Example: Store grading results
        """
        if not self.initialized:
            logger.error("Database not initialized")
            return False
        
        try:
            # Update submission status in PostgreSQL
            with get_postgres_session() as session:
                query = text("""
                    UPDATE submissions 
                    SET status = 'graded'
                    WHERE submission_id = :submission_id
                """)
                session.execute(query, {'submission_id': submission_id})
            
            # Store detailed grading results in MongoDB
            mongo_collection = get_mongo_collection("grading_results")
            document = {
                "submission_id": submission_id,
                "grading_results": grading_results,
                "total_score": grading_results.get("total_score", 0),
                "max_score": grading_results.get("max_score", 100),
                "question_scores": grading_results.get("question_scores", {}),
                "graded_at": datetime.utcnow(),
                "status": "graded"
            }
            
            result = mongo_collection.insert_one(document)
            logger.info(f"✅ Stored grading results: {result.inserted_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing grading results: {e}")
            return False
    
    def get_analytics_data(self, course_id: str) -> Dict[str, Any]:
        """
        Example: Get analytics data combining PostgreSQL and MongoDB
        """
        if not self.initialized:
            logger.error("Database not initialized")
            return {}
        
        try:
            analytics = {}
            
            # Get course and submission statistics from PostgreSQL
            with get_postgres_session() as session:
                # Get total submissions
                query = text("""
                    SELECT COUNT(*) as total_submissions,
                           COUNT(CASE WHEN s.status = 'graded' THEN 1 END) as graded_submissions
                    FROM submissions s
                    JOIN course_exam ce ON s.course_exam_id = ce.course_exam_id
                    WHERE ce.course_id = :course_id
                """)
                
                result = session.execute(query, {'course_id': course_id})
                stats = result.fetchone()
                
                analytics['total_submissions'] = stats[0]
                analytics['graded_submissions'] = stats[1]
            
            # Get score statistics from MongoDB
            mongo_collection = get_mongo_collection("grading_results")
            pipeline = [
                {
                    "$lookup": {
                        "from": "student_answers",
                        "localField": "submission_id",
                        "foreignField": "submission_id",
                        "as": "submission_info"
                    }
                },
                {
                    "$match": {
                        "submission_info.course_id": course_id
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "avg_score": {"$avg": "$total_score"},
                        "max_score": {"$max": "$total_score"},
                        "min_score": {"$min": "$total_score"}
                    }
                }
            ]
            
            score_stats = list(mongo_collection.aggregate(pipeline))
            if score_stats:
                analytics['average_score'] = score_stats[0].get('avg_score', 0)
                analytics['highest_score'] = score_stats[0].get('max_score', 0)
                analytics['lowest_score'] = score_stats[0].get('min_score', 0)
            
            logger.info(f"✅ Generated analytics for course {course_id}")
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Error getting analytics: {e}")
            return {}
    
    def cleanup(self):
        """Clean up database connections"""
        if self.initialized:
            close_database_connections()
            logger.info("🛑 Database connections closed")

def demo_usage():
    """
    Demonstrate how to use the unified connector in your grading system
    """
    logger.info("=== 🎓 Grading System Database Integration Demo ===")
    
    # Initialize the grading system database
    grading_db = GradingSystemDatabase()
    
    if not grading_db.initialize():
        logger.error("❌ Failed to initialize database connections")
        return False
    
    logger.info("✅ Database connections initialized successfully!")
    
    try:
        # Example 1: Store answer key
        logger.info("📝 Example 1: Storing answer key...")
        answer_key = {
            "1": {"question": "What is 2+2?", "answer": "4", "points": 10},
            "2": {"question": "What is the capital of France?", "answer": "Paris", "points": 10},
            "3": {"question": "Who wrote Romeo and Juliet?", "answer": "William Shakespeare", "points": 15}
        }
        grading_db.store_answer_key(exam_id=1, answer_key_data=answer_key)
        
        # Example 2: Store student submission
        logger.info("📄 Example 2: Storing student submission...")
        submission_data = {
            "submission_id": "sub_001",
            "file_path": "/uploads/student_001_exam_001.pdf",
            "processed_answers": {
                "1": "4",
                "2": "Paris",
                "3": "Shakespeare"
            },
            "ocr_text": "1. 4\n2. Paris\n3. Shakespeare"
        }
        # Note: This would fail because the tables don't exist yet, but shows the pattern
        # grading_db.store_student_submission("student_001", "CS101", 1, submission_data)
        
        # Example 3: Store grading results
        logger.info("🎯 Example 3: Storing grading results...")
        grading_results = {
            "total_score": 35,
            "max_score": 35,
            "question_scores": {
                "1": {"score": 10, "max_score": 10, "feedback": "Correct!"},
                "2": {"score": 10, "max_score": 10, "feedback": "Correct!"},
                "3": {"score": 15, "max_score": 15, "feedback": "Perfect answer!"}
            },
            "overall_feedback": "Excellent work!"
        }
        grading_db.store_grading_results("sub_001", grading_results)
        
        logger.info("🎉 Demo completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        return False
    
    finally:
        grading_db.cleanup()

if __name__ == "__main__":
    success = demo_usage()
    sys.exit(0 if success else 1)
