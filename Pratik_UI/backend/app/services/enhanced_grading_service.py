"""
Enhanced Grading Service with Unified Database Connector

This is an updated version of your grading service that uses the unified connector
to access both PostgreSQL (for structured data) and MongoDB (for processed content).
"""

from typing import Dict, List, Optional, Any
import json
import re
import logging
from datetime import datetime

# Import the unified connector
from app.db.connector import get_postgres_session, get_mongo_collection
from sqlalchemy import text

# For ML processing (install these if needed)
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedGradingService:
    """
    Enhanced grading service that uses both PostgreSQL and MongoDB
    for comprehensive grading functionality
    """
    
    def __init__(self):
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy English model not found. Install with: python -m spacy download en_core_web_sm")
    
    def grade_submission(self, submission_id: str, answer_key: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main grading method that combines PostgreSQL metadata with MongoDB content
        
        Args:
            submission_id: The submission ID to grade
            answer_key: The answer key for comparison
            
        Returns:
            Dict containing grading results
        """
        try:
            # Get submission metadata from PostgreSQL
            submission_metadata = self._get_submission_metadata(submission_id)
            if not submission_metadata:
                raise ValueError(f"Submission {submission_id} not found")
            
            # Get processed content from MongoDB
            processed_content = self._get_processed_content(submission_id)
            if not processed_content:
                raise ValueError(f"No processed content found for submission {submission_id}")
            
            # Perform grading
            grading_results = self._perform_grading(
                processed_content.get('processed_answers', {}),
                answer_key,
                processed_content.get('ocr_text', '')
            )
            
            # Store results
            self._store_grading_results(submission_id, grading_results)
            
            # Update submission status
            self._update_submission_status(submission_id, 'graded')
            
            return grading_results
            
        except Exception as e:
            logger.error(f"Error grading submission {submission_id}: {e}")
            raise
    
    def _get_submission_metadata(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get submission metadata from PostgreSQL"""
        try:
            with get_postgres_session() as session:
                query = text("""
                    SELECT s.submission_id, s.student_id, s.status, s.file_path,
                           ce.course_id, ce.exam_id,
                           e.exam_type, e.answer_key_file_path
                    FROM submissions s
                    JOIN course_exam ce ON s.course_exam_id = ce.course_exam_id
                    JOIN exams e ON ce.exam_id = e.exam_id
                    WHERE s.submission_id = :submission_id
                """)
                
                result = session.execute(query, {'submission_id': submission_id})
                row = result.fetchone()
                
                if row:
                    return {
                        'submission_id': row[0],
                        'student_id': row[1],
                        'status': row[2],
                        'file_path': row[3],
                        'course_id': row[4],
                        'exam_id': row[5],
                        'exam_type': row[6],
                        'answer_key_file_path': row[7]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting submission metadata: {e}")
            return None
    
    def _get_processed_content(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Get processed content from MongoDB"""
        try:
            collection = get_mongo_collection("student_answers")
            document = collection.find_one({"submission_id": submission_id})
            return document
            
        except Exception as e:
            logger.error(f"Error getting processed content: {e}")
            return None
    
    def _perform_grading(self, student_answers: Dict[str, str], 
                        answer_key: Dict[str, Any], ocr_text: str) -> Dict[str, Any]:
        """
        Perform the actual grading logic
        
        Args:
            student_answers: Student's processed answers
            answer_key: Correct answers with metadata
            ocr_text: Raw OCR text for additional analysis
            
        Returns:
            Comprehensive grading results
        """
        results = {
            'question_scores': {},
            'total_score': 0,
            'max_score': 0,
            'percentage': 0,
            'feedback': {},
            'overall_feedback': '',
            'graded_at': datetime.utcnow().isoformat(),
            'grading_details': {}
        }
        
        # Grade each question
        for question_id, answer_info in answer_key.items():
            if question_id not in student_answers:
                # Question not attempted
                results['question_scores'][question_id] = {
                    'score': 0,
                    'max_score': answer_info.get('points', 10),
                    'feedback': 'Question not attempted',
                    'status': 'not_attempted'
                }
                continue
            
            student_answer = student_answers[question_id]
            correct_answer = answer_info.get('answer', '')
            max_points = answer_info.get('points', 10)
            
            # Grade the individual question
            question_result = self._grade_question(
                student_answer, 
                correct_answer, 
                max_points,
                answer_info.get('type', 'text'),
                answer_info.get('grading_criteria', {})
            )
            
            results['question_scores'][question_id] = question_result
            results['total_score'] += question_result['score']
            results['max_score'] += max_points
        
        # Calculate percentage
        if results['max_score'] > 0:
            results['percentage'] = (results['total_score'] / results['max_score']) * 100
        
        # Generate overall feedback
        results['overall_feedback'] = self._generate_overall_feedback(results, ocr_text)
        
        # Add grading details
        results['grading_details'] = {
            'method': 'ai_automated',
            'confidence': self._calculate_confidence_score(results),
            'needs_review': self._needs_manual_review(results),
            'ocr_quality': self._assess_ocr_quality(ocr_text)
        }
        
        return results
    
    def _grade_question(self, student_answer: str, correct_answer: str, 
                       max_points: int, question_type: str = 'text',
                       grading_criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Grade an individual question
        
        Args:
            student_answer: Student's answer
            correct_answer: Correct answer
            max_points: Maximum points for this question
            question_type: Type of question (text, multiple_choice, numeric, etc.)
            grading_criteria: Additional grading criteria
            
        Returns:
            Question grading result
        """
        result = {
            'score': 0,
            'max_score': max_points,
            'feedback': '',
            'status': 'graded',
            'similarity_score': 0.0,
            'keywords_found': [],
            'deductions': []
        }
        
        if not student_answer or not student_answer.strip():
            result['feedback'] = 'No answer provided'
            result['status'] = 'not_attempted'
            return result
        
        # Clean answers for comparison
        student_clean = self._clean_text(student_answer)
        correct_clean = self._clean_text(correct_answer)
        
        if question_type == 'multiple_choice':
            # Exact match for multiple choice
            if student_clean.lower() == correct_clean.lower():
                result['score'] = max_points
                result['feedback'] = 'Correct answer'
            else:
                result['feedback'] = f'Incorrect. Correct answer: {correct_answer}'
        
        elif question_type == 'numeric':
            # Numeric comparison with tolerance
            score = self._grade_numeric_answer(student_clean, correct_clean, max_points)
            result['score'] = score
            result['feedback'] = 'Correct' if score == max_points else f'Incorrect. Correct answer: {correct_answer}'
        
        else:
            # Text-based grading
            result = self._grade_text_answer(student_answer, correct_answer, max_points, grading_criteria)
        
        return result
    
    def _grade_text_answer(self, student_answer: str, correct_answer: str, 
                          max_points: int, grading_criteria: Dict[str, Any] = None) -> Dict[str, Any]:
        """Grade text-based answers using multiple techniques"""
        
        result = {
            'score': 0,
            'max_score': max_points,
            'feedback': '',
            'status': 'graded',
            'similarity_score': 0.0,
            'keywords_found': [],
            'deductions': []
        }
        
        # 1. Keyword matching
        keyword_score = self._calculate_keyword_score(student_answer, correct_answer)
        
        # 2. Semantic similarity (if available)
        semantic_score = 0.0
        if self.nlp:
            semantic_score = self._calculate_semantic_similarity(student_answer, correct_answer)
        
        # 3. Length and completeness
        completeness_score = self._calculate_completeness_score(student_answer, correct_answer)
        
        # Combine scores
        weights = grading_criteria.get('weights', {
            'keywords': 0.4,
            'semantic': 0.4,
            'completeness': 0.2
        }) if grading_criteria else {'keywords': 0.4, 'semantic': 0.4, 'completeness': 0.2}
        
        final_score = (
            keyword_score * weights.get('keywords', 0.4) +
            semantic_score * weights.get('semantic', 0.4) +
            completeness_score * weights.get('completeness', 0.2)
        )
        
        result['score'] = min(final_score * max_points, max_points)
        result['similarity_score'] = semantic_score
        result['feedback'] = self._generate_question_feedback(
            final_score, keyword_score, semantic_score, completeness_score
        )
        
        return result
    
    def _calculate_keyword_score(self, student_answer: str, correct_answer: str) -> float:
        """Calculate score based on keyword matching"""
        correct_words = set(self._clean_text(correct_answer).lower().split())
        student_words = set(self._clean_text(student_answer).lower().split())
        
        if not correct_words:
            return 0.0
        
        # Calculate overlap
        overlap = len(correct_words.intersection(student_words))
        return overlap / len(correct_words)
    
    def _calculate_semantic_similarity(self, student_answer: str, correct_answer: str) -> float:
        """Calculate semantic similarity using spaCy"""
        if not self.nlp:
            return 0.0
        
        try:
            doc1 = self.nlp(student_answer)
            doc2 = self.nlp(correct_answer)
            return doc1.similarity(doc2)
        except Exception:
            return 0.0
    
    def _calculate_completeness_score(self, student_answer: str, correct_answer: str) -> float:
        """Calculate completeness based on length ratio"""
        student_len = len(student_answer.split())
        correct_len = len(correct_answer.split())
        
        if correct_len == 0:
            return 1.0 if student_len == 0 else 0.0
        
        ratio = student_len / correct_len
        # Optimal ratio is around 0.8-1.2 of the correct answer length
        if 0.8 <= ratio <= 1.2:
            return 1.0
        elif ratio < 0.8:
            return ratio / 0.8
        else:
            return max(0.0, 1.0 - (ratio - 1.2) * 0.5)
    
    def _grade_numeric_answer(self, student_answer: str, correct_answer: str, max_points: int) -> float:
        """Grade numeric answers with tolerance"""
        try:
            student_num = float(re.findall(r'-?\d+\.?\d*', student_answer)[0])
            correct_num = float(re.findall(r'-?\d+\.?\d*', correct_answer)[0])
            
            # 5% tolerance for numeric answers
            tolerance = abs(correct_num * 0.05)
            if abs(student_num - correct_num) <= tolerance:
                return max_points
            else:
                return 0.0
        except (ValueError, IndexError):
            return 0.0
    
    def _clean_text(self, text: str) -> str:
        """Clean text for comparison"""
        # Remove extra whitespace, punctuation, etc.
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _generate_question_feedback(self, final_score: float, keyword_score: float, 
                                  semantic_score: float, completeness_score: float) -> str:
        """Generate detailed feedback for a question"""
        if final_score >= 0.9:
            return "Excellent answer! Complete and accurate."
        elif final_score >= 0.7:
            feedback = "Good answer. "
            if keyword_score < 0.7:
                feedback += "Consider including more key terms. "
            if completeness_score < 0.7:
                feedback += "Could be more detailed. "
            return feedback
        elif final_score >= 0.5:
            return "Partially correct. Missing some key concepts or details."
        else:
            return "Needs improvement. Please review the material and provide more accurate information."
    
    def _generate_overall_feedback(self, results: Dict[str, Any], ocr_text: str) -> str:
        """Generate overall feedback for the submission"""
        percentage = results['percentage']
        
        if percentage >= 90:
            return "Outstanding work! Excellent understanding demonstrated across all questions."
        elif percentage >= 80:
            return "Very good work! Minor areas for improvement identified."
        elif percentage >= 70:
            return "Good effort. Some concepts need further review."
        elif percentage >= 60:
            return "Fair performance. Significant improvement needed in several areas."
        else:
            return "Needs substantial improvement. Please review the material thoroughly."
    
    def _calculate_confidence_score(self, results: Dict[str, Any]) -> float:
        """Calculate confidence in the automated grading"""
        # Simple confidence based on average similarity scores
        similarity_scores = [
            q.get('similarity_score', 0) for q in results['question_scores'].values()
        ]
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
    
    def _needs_manual_review(self, results: Dict[str, Any]) -> bool:
        """Determine if submission needs manual review"""
        confidence = self._calculate_confidence_score(results)
        
        # Needs review if confidence is low or scores are borderline
        if confidence < 0.6:
            return True
        
        # Check for borderline scores
        for q_result in results['question_scores'].values():
            score_ratio = q_result['score'] / q_result['max_score']
            if 0.4 <= score_ratio <= 0.6:  # Borderline scores
                return True
        
        return False
    
    def _assess_ocr_quality(self, ocr_text: str) -> Dict[str, Any]:
        """Assess the quality of OCR text"""
        quality_indicators = {
            'has_artifacts': bool(re.search(r'[???????????????]', ocr_text)),
            'very_short': len(ocr_text.split()) < 20,
            'unusual_chars': len(re.findall(r'[^a-zA-Z0-9\s.,!?()-]', ocr_text)) > 10,
            'word_count': len(ocr_text.split()),
            'estimated_quality': 'high'
        }
        
        issues = sum([
            quality_indicators['has_artifacts'],
            quality_indicators['very_short'],
            quality_indicators['unusual_chars']
        ])
        
        if issues == 0:
            quality_indicators['estimated_quality'] = 'high'
        elif issues == 1:
            quality_indicators['estimated_quality'] = 'medium'
        else:
            quality_indicators['estimated_quality'] = 'low'
        
        return quality_indicators
    
    def _store_grading_results(self, submission_id: str, results: Dict[str, Any]) -> bool:
        """Store grading results in MongoDB"""
        try:
            collection = get_mongo_collection("grading_results")
            document = {
                "submission_id": submission_id,
                "results": results,
                "created_at": datetime.utcnow(),
                "version": "2.0"  # Version of grading algorithm
            }
            
            # Upsert to handle re-grading
            collection.replace_one(
                {"submission_id": submission_id},
                document,
                upsert=True
            )
            
            logger.info(f"Stored grading results for submission {submission_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing grading results: {e}")
            return False
    
    def _update_submission_status(self, submission_id: str, status: str) -> bool:
        """Update submission status in PostgreSQL"""
        try:
            with get_postgres_session() as session:
                query = text("""
                    UPDATE submissions 
                    SET status = :status 
                    WHERE submission_id = :submission_id
                """)
                session.execute(query, {
                    'status': status, 
                    'submission_id': submission_id
                })
                
            logger.info(f"Updated submission {submission_id} status to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating submission status: {e}")
            return False
    
    def get_answer_key(self, exam_id: int) -> Optional[Dict[str, Any]]:
        """Get answer key from MongoDB"""
        try:
            collection = get_mongo_collection("answer_keys")
            document = collection.find_one(
                {"exam_id": exam_id, "status": "active"},
                sort=[("created_at", -1)]  # Get latest
            )
            
            if document:
                return document.get('answer_key', {})
            return None
            
        except Exception as e:
            logger.error(f"Error getting answer key: {e}")
            return None
    
    def batch_grade_submissions(self, exam_id: int) -> Dict[str, Any]:
        """Grade all submissions for an exam"""
        try:
            # Get answer key
            answer_key = self.get_answer_key(exam_id)
            if not answer_key:
                raise ValueError(f"No answer key found for exam {exam_id}")
            
            # Get all submissions for this exam
            with get_postgres_session() as session:
                query = text("""
                    SELECT s.submission_id
                    FROM submissions s
                    JOIN course_exam ce ON s.course_exam_id = ce.course_exam_id
                    WHERE ce.exam_id = :exam_id AND s.status = 'uploaded'
                """)
                
                result = session.execute(query, {'exam_id': exam_id})
                submission_ids = [row[0] for row in result.fetchall()]
            
            # Grade each submission
            results = {
                'exam_id': exam_id,
                'total_submissions': len(submission_ids),
                'graded_successfully': 0,
                'failed_submissions': [],
                'summary': {}
            }
            
            for submission_id in submission_ids:
                try:
                    grading_result = self.grade_submission(submission_id, answer_key)
                    results['graded_successfully'] += 1
                except Exception as e:
                    logger.error(f"Failed to grade submission {submission_id}: {e}")
                    results['failed_submissions'].append({
                        'submission_id': submission_id,
                        'error': str(e)
                    })
            
            logger.info(f"Batch grading completed for exam {exam_id}: {results['graded_successfully']}/{results['total_submissions']} successful")
            return results
            
        except Exception as e:
            logger.error(f"Error in batch grading: {e}")
            raise

# Usage example and convenience functions
def grade_single_submission(submission_id: str, exam_id: int) -> Dict[str, Any]:
    """Convenience function to grade a single submission"""
    service = EnhancedGradingService()
    
    # Get answer key
    answer_key = service.get_answer_key(exam_id)
    if not answer_key:
        raise ValueError(f"No answer key found for exam {exam_id}")
    
    return service.grade_submission(submission_id, answer_key)

def grade_all_submissions_for_exam(exam_id: int) -> Dict[str, Any]:
    """Convenience function to grade all submissions for an exam"""
    service = EnhancedGradingService()
    return service.batch_grade_submissions(exam_id)


# Global instance for easy importing
enhanced_grading_service = EnhancedGradingService()
