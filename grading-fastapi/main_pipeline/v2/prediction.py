"""
Grade prediction utilities.
"""

import numpy as np
import joblib
import logging
from pathlib import Path
from .config import GRADE_MODEL_PATH

logger = logging.getLogger(__name__)

class GradePredictor:
    """Class to handle grade predictions"""
    
    def __init__(self, model_path=None):
        """Initialize the grade predictor with a trained model"""
        if model_path is None:
            model_path = GRADE_MODEL_PATH
            
        try:
            self.model_bundle = joblib.load(model_path)
            self.model = self.model_bundle['model']
            logger.info(f"Grade prediction model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load grade prediction model: {str(e)}")
            raise e
    
    def predict_grade(self, tfidf_score, full_similarity_score, mean_similarity_score):
        """
        Predict grade based on similarity scores.
        
        Args:
            tfidf_score: TF-IDF similarity score
            full_similarity_score: Full embedding similarity score
            mean_similarity_score: Mean structure similarity score
            
        Returns:
            Predicted grade
        """
        try:
            input_data = np.array([[tfidf_score, full_similarity_score, mean_similarity_score]])
            prediction = self.model.predict(input_data)[0]
            return prediction
        except Exception as e:
            logger.error(f"Error during grade prediction: {str(e)}")
            return "Error"

# Global predictor instance
_predictor = None

def get_predictor():
    """Get or create global predictor instance"""
    global _predictor
    if _predictor is None:
        _predictor = GradePredictor()
    return _predictor

def run_prediction(tfidf_score, full_similarity_score, mean_similarity_score):
    """Convenience function for running predictions"""
    return get_predictor().predict_grade(tfidf_score, full_similarity_score, mean_similarity_score)
