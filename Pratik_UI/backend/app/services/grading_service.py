from sqlalchemy.orm import Session
from app.models.models import Submission, Assignment, GradingCriteria
import re
import json
from typing import Dict, List

# Handle optional ML dependencies
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

class GradingService:
    def __init__(self, db: Session):
        self.db = db
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                # Fallback if spacy model is not installed
                self.nlp = None
    
    def auto_grade_submission(self, submission_id: int) -> float:
        """Automatically grade a submission based on criteria"""
        
        submission = self.db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            raise ValueError("Submission not found")
        
        assignment = submission.assignment
        if not assignment:
            raise ValueError("Assignment not found")
        
        # Get grading criteria for the assignment
        criteria = self.db.query(GradingCriteria).filter(
            GradingCriteria.assignment_id == assignment.id
        ).all()
        
        if not criteria:
            # If no specific criteria, use basic scoring
            return self._basic_scoring(submission.ocr_text, assignment.max_score)
        
        # Calculate score based on criteria
        total_score = 0.0
        for criterion in criteria:
            criterion_score = self._score_criterion(submission.ocr_text, criterion)
            total_score += criterion_score
        
        # Normalize to assignment max score
        max_possible = sum(c.max_points for c in criteria)
        if max_possible > 0:
            normalized_score = (total_score / max_possible) * assignment.max_score
        else:
            normalized_score = self._basic_scoring(submission.ocr_text, assignment.max_score)
        
        return min(normalized_score, assignment.max_score)
    
    def _basic_scoring(self, text: str, max_score: float) -> float:
        """Basic scoring when no specific criteria are available"""
        
        if not text or not text.strip():
            return 0.0
        
        # Basic metrics
        word_count = len(text.split())
        sentence_count = len([s for s in text.split('.') if s.strip()])
        
        # Simple heuristics
        completeness_score = min(word_count / 100, 1.0) * 0.3  # 30% for completeness
        structure_score = min(sentence_count / 5, 1.0) * 0.2   # 20% for structure
        
        # Check for common academic indicators
        academic_indicators = [
            'because', 'therefore', 'however', 'furthermore', 'moreover',
            'in conclusion', 'for example', 'such as', 'according to'
        ]
        
        indicator_count = sum(1 for indicator in academic_indicators if indicator in text.lower())
        quality_score = min(indicator_count / 3, 1.0) * 0.3  # 30% for quality
        
        # Spelling and grammar (basic check)
        grammar_score = self._basic_grammar_check(text) * 0.2  # 20% for grammar
        
        total_score = (completeness_score + structure_score + quality_score + grammar_score) * max_score
        
        return total_score
    
    def _score_criterion(self, text: str, criterion: GradingCriteria) -> float:
        """Score text based on a specific grading criterion"""
        
        if not text or not text.strip():
            return 0.0
        
        # Parse keywords from criterion
        keywords = []
        if criterion.keywords:
            try:
                keywords = json.loads(criterion.keywords)
            except json.JSONDecodeError:
                keywords = criterion.keywords.split(',')
        
        if not keywords:
            return criterion.max_points * 0.5  # Default partial credit
        
        # Keyword matching score
        keyword_score = self._calculate_keyword_score(text, keywords)
        
        # Semantic similarity score (if spacy is available)
        semantic_score = 0.0
        if self.nlp and criterion.description:
            semantic_score = self._calculate_semantic_score(text, criterion.description)
        
        # Combine scores
        final_score = (keyword_score * 0.7 + semantic_score * 0.3) * criterion.max_points
        
        return min(final_score, criterion.max_points)
    
    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> float:
        """Calculate score based on keyword presence"""
        
        text_lower = text.lower()
        found_keywords = 0
        
        for keyword in keywords:
            keyword = keyword.strip().lower()
            if keyword in text_lower:
                found_keywords += 1
        
        return found_keywords / len(keywords) if keywords else 0.0
    
    def _calculate_semantic_score(self, text: str, reference_text: str) -> float:
        """Calculate semantic similarity score using spaCy"""
        
        if not self.nlp:
            return 0.0
        
        try:
            doc1 = self.nlp(text)
            doc2 = self.nlp(reference_text)
            
            # Calculate similarity
            similarity = doc1.similarity(doc2)
            return similarity
            
        except Exception:
            return 0.0
    
    def _basic_grammar_check(self, text: str) -> float:
        """Basic grammar and spelling check"""
        
        # Simple checks
        issues = 0
        total_checks = 0
        
        # Check for common issues
        sentences = text.split('.')
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            total_checks += 1
            
            # Check if sentence starts with capital letter
            stripped = sentence.strip()
            if stripped and not stripped[0].isupper():
                issues += 1
            
            # Check for repeated words
            words = stripped.split()
            for i in range(len(words) - 1):
                if words[i].lower() == words[i + 1].lower():
                    issues += 1
                    break
        
        if total_checks == 0:
            return 0.0
        
        grammar_score = max(0, 1 - (issues / total_checks))
        return grammar_score
    
    def create_grading_criteria(self, assignment_id: int, criteria_data: List[Dict]) -> List[GradingCriteria]:
        """Create grading criteria for an assignment"""
        
        criteria_list = []
        
        for data in criteria_data:
            criterion = GradingCriteria(
                assignment_id=assignment_id,
                criterion_name=data['name'],
                max_points=data['max_points'],
                description=data.get('description', ''),
                keywords=json.dumps(data.get('keywords', []))
            )
            
            self.db.add(criterion)
            criteria_list.append(criterion)
        
        self.db.commit()
        return criteria_list
    
    def get_grading_suggestions(self, submission_id: int) -> Dict:
        """Get AI suggestions for grading"""
        
        submission = self.db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            return {}
        
        text = submission.ocr_text
        if not text:
            return {"suggestions": ["No text found in submission"]}
        
        suggestions = []
        
        # Analyze text structure
        word_count = len(text.split())
        sentence_count = len([s for s in text.split('.') if s.strip()])
        
        if word_count < 50:
            suggestions.append("Submission appears to be quite short. Consider checking if all content was captured.")
        
        if sentence_count < 3:
            suggestions.append("Limited sentence structure detected. May need manual review.")
        
        # Check for potential issues
        if any(char in text for char in ['???', '???', '???']):
            suggestions.append("OCR artifacts detected. Manual review recommended for accuracy.")
        
        # Positive indicators
        academic_words = ['analysis', 'conclusion', 'evidence', 'argument', 'theory']
        found_academic = [word for word in academic_words if word.lower() in text.lower()]
        
        if found_academic:
            suggestions.append(f"Good academic language detected: {', '.join(found_academic)}")
        
        return {
            "suggestions": suggestions,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "confidence": submission.auto_score / submission.assignment.max_score if submission.auto_score else 0
        }
