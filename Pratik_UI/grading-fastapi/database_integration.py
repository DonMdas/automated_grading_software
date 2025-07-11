"""
Database Integration Layer for Grading FastAPI

This module integrates the existing grading FastAPI with the unified database connector.
It doesn't change the core grading logic, only adds database persistence.
"""

import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys
import os

# Add the backend path to import the connector
backend_path = str(Path(__file__).parent.parent.parent / "backend")
sys.path.insert(0, backend_path)

# Import the unified database connector
from app.db.connector import (
    initialize_database_connections,
    get_postgres_session,
    get_mongo_collection,
    close_database_connections
)
from sqlalchemy import text

logger = logging.getLogger(__name__)

class GradingDatabaseIntegration:
    """
    Integration layer between the grading FastAPI and the unified database.
    Handles storing/retrieving data without changing grading logic.
    """
    
    def __init__(self):
        self.initialized = False
    
    def initialize(self) -> bool:
        """Initialize database connections"""
        try:
            self.initialized = initialize_database_connections()
            if self.initialized:
                logger.info("✅ Grading database integration initialized")
            else:
                logger.error("❌ Failed to initialize database connections")
            return self.initialized
        except Exception as e:
            logger.error(f"❌ Error initializing grading database: {e}")
            return False
    
    def store_exam_metadata(self, exam_name: str, exam_type: str, teacher_id: int = None) -> int:
        """
        Store exam metadata in PostgreSQL
        
        Args:
            exam_name: Name of the exam
            exam_type: Type of exam
            teacher_id: Optional teacher ID
            
        Returns:
            exam_id: The created exam ID
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            with get_postgres_session() as session:
                # Insert exam record
                query = text("""
                    INSERT INTO exams (exam_type, created_at)
                    VALUES (:exam_type, NOW())
                    RETURNING exam_id
                """)
                result = session.execute(query, {'exam_type': exam_type})
                exam_id = result.fetchone()[0]
                
                logger.info(f"✅ Created exam metadata: {exam_name} (ID: {exam_id})")
                return exam_id
                
        except Exception as e:
            logger.error(f"❌ Error storing exam metadata: {e}")
            raise
    
    def store_answer_key(self, exam_id: int, answer_key_data: Dict[str, Any], 
                        file_path: str = None) -> bool:
        """
        Store answer key in MongoDB
        
        Args:
            exam_id: The exam ID
            answer_key_data: The processed answer key data
            file_path: Optional path to the original file
            
        Returns:
            bool: Success status
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            collection = get_mongo_collection("answer_keys")
            
            document = {
                "exam_id": exam_id,
                "answer_key": answer_key_data,
                "file_path": file_path,
                "created_at": datetime.utcnow(),
                "status": "active",
                "metadata": {
                    "total_questions": len(answer_key_data),
                    "question_types": self._analyze_question_types(answer_key_data)
                }
            }
            
            # Upsert to handle updates
            collection.replace_one(
                {"exam_id": exam_id},
                document,
                upsert=True
            )
            
            logger.info(f"✅ Stored answer key for exam {exam_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing answer key: {e}")
            return False
    
    def store_student_submission(self, exam_id: int, student_id: str, 
                               file_path: str, processed_data: Dict[str, Any] = None) -> str:
        """
        Store student submission metadata and processed data
        
        Args:
            exam_id: The exam ID
            student_id: Student identifier
            file_path: Path to the submission file
            processed_data: OCR processed data
            
        Returns:
            submission_id: The generated submission ID
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        submission_id = str(uuid.uuid4())
        
        try:
            # Store metadata in PostgreSQL (simplified - adjust to your schema)
            with get_postgres_session() as session:
                # This assumes you have the tables set up
                # Adjust the query based on your actual schema
                logger.info(f"📝 Would store submission metadata for {student_id} in PostgreSQL")
            
            # Store processed data in MongoDB
            if processed_data:
                collection = get_mongo_collection("student_submissions")
                document = {
                    "submission_id": submission_id,
                    "exam_id": exam_id,
                    "student_id": student_id,
                    "file_path": file_path,
                    "processed_answers": processed_data.get("answers", {}),
                    "ocr_text": processed_data.get("raw_text", ""),
                    "created_at": datetime.utcnow(),
                    "status": "processed"
                }
                
                collection.insert_one(document)
                logger.info(f"✅ Stored student submission data: {submission_id}")
            
            return submission_id
            
        except Exception as e:
            logger.error(f"❌ Error storing student submission: {e}")
            raise
    
    def store_grading_results(self, submission_id: str, grading_results: Dict[str, Any]) -> bool:
        """
        Store grading results in MongoDB
        
        Args:
            submission_id: The submission ID
            grading_results: Complete grading results from the grading engine
            
        Returns:
            bool: Success status
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            collection = get_mongo_collection("grading_results")
            
            document = {
                "submission_id": submission_id,
                "grading_results": grading_results,
                "graded_at": datetime.utcnow(),
                "version": "grading_fastapi_v2",
                "needs_review": self._needs_review(grading_results),
                "summary": {
                    "total_score": grading_results.get("total_score", 0),
                    "max_score": grading_results.get("max_score", 100),
                    "percentage": grading_results.get("percentage", 0),
                    "question_count": len(grading_results.get("question_scores", {}))
                }
            }
            
            collection.replace_one(
                {"submission_id": submission_id},
                document,
                upsert=True
            )
            
            logger.info(f"✅ Stored grading results for submission {submission_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing grading results: {e}")
            return False
    
    def get_exam_submissions(self, exam_id: int) -> List[Dict[str, Any]]:
        """
        Get all submissions for an exam
        
        Args:
            exam_id: The exam ID
            
        Returns:
            List of submission data
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            collection = get_mongo_collection("student_submissions")
            submissions = list(collection.find({"exam_id": exam_id}))
            
            # Convert ObjectId to string for JSON serialization
            for submission in submissions:
                submission["_id"] = str(submission["_id"])
            
            logger.info(f"📊 Retrieved {len(submissions)} submissions for exam {exam_id}")
            return submissions
            
        except Exception as e:
            logger.error(f"❌ Error getting exam submissions: {e}")
            return []
    
    def get_grading_results(self, exam_id: int) -> Dict[str, Any]:
        """
        Get aggregated grading results for an exam
        
        Args:
            exam_id: The exam ID
            
        Returns:
            Aggregated grading results
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            # Get submissions for this exam
            submissions = self.get_exam_submissions(exam_id)
            submission_ids = [sub["submission_id"] for sub in submissions]
            
            # Get grading results
            collection = get_mongo_collection("grading_results")
            results = list(collection.find({"submission_id": {"$in": submission_ids}}))
            
            # Aggregate results
            aggregated = {
                "exam_id": exam_id,
                "total_submissions": len(submissions),
                "graded_submissions": len(results),
                "results": {}
            }
            
            for result in results:
                submission_id = result["submission_id"]
                # Find corresponding submission
                submission = next((s for s in submissions if s["submission_id"] == submission_id), None)
                if submission:
                    aggregated["results"][submission["student_id"]] = {
                        "submission_id": submission_id,
                        "grading_results": result["grading_results"],
                        "summary": result.get("summary", {}),
                        "needs_review": result.get("needs_review", False),
                        "graded_at": result.get("graded_at")
                    }
            
            logger.info(f"📊 Retrieved grading results for exam {exam_id}: {len(results)} graded")
            return aggregated
            
        except Exception as e:
            logger.error(f"❌ Error getting grading results: {e}")
            return {}
    
    def get_answer_key(self, exam_id: int) -> Optional[Dict[str, Any]]:
        """
        Get answer key for an exam
        
        Args:
            exam_id: The exam ID
            
        Returns:
            Answer key data or None
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            collection = get_mongo_collection("answer_keys")
            document = collection.find_one({"exam_id": exam_id, "status": "active"})
            
            if document:
                return document.get("answer_key", {})
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting answer key: {e}")
            return None
    
    def update_submission_status(self, submission_id: str, status: str) -> bool:
        """
        Update submission status
        
        Args:
            submission_id: The submission ID
            status: New status
            
        Returns:
            bool: Success status
        """
        if not self.initialized:
            raise RuntimeError("Database not initialized")
        
        try:
            collection = get_mongo_collection("student_submissions")
            result = collection.update_one(
                {"submission_id": submission_id},
                {"$set": {"status": status, "updated_at": datetime.utcnow()}}
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"✅ Updated submission {submission_id} status to {status}")
            else:
                logger.warning(f"⚠️ No submission found with ID {submission_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error updating submission status: {e}")
            return False
    
    def _analyze_question_types(self, answer_key: Dict[str, Any]) -> Dict[str, int]:
        """Analyze question types in answer key"""
        types = {"text": 0, "numeric": 0, "multiple_choice": 0}
        
        for q_data in answer_key.values():
            answer = q_data.get("answer", "")
            if answer.isdigit() or any(c in answer for c in "0123456789."):
                types["numeric"] += 1
            elif len(answer.split()) == 1 and len(answer) < 5:
                types["multiple_choice"] += 1
            else:
                types["text"] += 1
        
        return types
    
    def _needs_review(self, grading_results: Dict[str, Any]) -> bool:
        """Determine if grading results need manual review"""
        # Simple heuristic - you can make this more sophisticated
        confidence_scores = []
        
        for q_result in grading_results.get("question_scores", {}).values():
            if isinstance(q_result, dict) and "confidence" in q_result:
                confidence_scores.append(q_result["confidence"])
        
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            return avg_confidence < 0.8  # Needs review if confidence < 80%
        
        return False
    
    def cleanup(self):
        """Clean up database connections"""
        if self.initialized:
            close_database_connections()
            logger.info("🛑 Grading database connections closed")

# Global instance
grading_db = GradingDatabaseIntegration()
