"""
Grade prediction functionality.
Handles model loading and prediction based on similarity scores.
"""

import numpy as np
import joblib
import logging
from typing import Union, List
from pathlib import Path

from .config import GRADE_MODEL_PATH
from .utils import safe_float_conversion

logger = logging.getLogger(__name__)


class GradePredictor:
    """Class to handle grade prediction using trained models."""
    
    def __init__(self, model_path: str = GRADE_MODEL_PATH):
        """
        Initialize the grade predictor.
        
        Args:
            model_path: Path to the trained model file
        """
        self.model_path = model_path
        self.model_bundle = None
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load the trained model from file."""
        try:
            if not Path(self.model_path).exists():
                logger.error(f"Model file not found: {self.model_path}")
                return
            
            self.model_bundle = joblib.load(self.model_path)
            
            # Extract model from bundle (handle different bundle formats)
            if isinstance(self.model_bundle, dict):
                self.model = self.model_bundle.get('model', self.model_bundle)
            else:
                self.model = self.model_bundle
            
            logger.info(f"Grade prediction model loaded successfully from {self.model_path}")
            
        except Exception as e:
            logger.error(f"Failed to load grade prediction model: {str(e)}")
            self.model = None
    
    def predict_grade(
        self, 
        tfidf_score: float, 
        full_similarity_score: float, 
        mean_structure_similarity: float
    ) -> Union[str, float]:
        """
        Predict grade based on similarity scores.
        
        Args:
            tfidf_score: TF-IDF similarity score
            full_similarity_score: Full text embedding similarity score
            mean_structure_similarity: Mean structure similarity score
            
        Returns:
            Predicted grade
        """
        if self.model is None:
            logger.warning("Model not loaded, returning default grade")
            return "Not Available"
        
        try:
            # Ensure all inputs are valid floats
            tfidf_score = safe_float_conversion(tfidf_score)
            full_similarity_score = safe_float_conversion(full_similarity_score)
            mean_structure_similarity = safe_float_conversion(mean_structure_similarity)
            
            # Prepare input data
            input_data = np.array([[tfidf_score, full_similarity_score, mean_structure_similarity]])
            
            # Make prediction
            prediction = self.model.predict(input_data)[0]
            
            logger.debug(f"Prediction input: {input_data.flatten()}, output: {prediction}")
            return prediction
            
        except Exception as e:
            logger.error(f"Error during grade prediction: {str(e)}")
            return "Error"
    
    def predict_batch(
        self, 
        features_list: List[List[float]]
    ) -> List[Union[str, float]]:
        """
        Predict grades for a batch of feature sets.
        
        Args:
            features_list: List of feature arrays [tfidf, full_sim, structure_sim]
            
        Returns:
            List of predicted grades
        """
        if self.model is None:
            logger.warning("Model not loaded, returning default grades")
            return ["Not Available"] * len(features_list)
        
        try:
            # Convert to numpy array and make predictions
            input_data = np.array(features_list)
            predictions = self.model.predict(input_data)
            
            return predictions.tolist()
            
        except Exception as e:
            logger.error(f"Error during batch grade prediction: {str(e)}")
            return ["Error"] * len(features_list)
    
    def is_model_loaded(self) -> bool:
        """Check if the model is successfully loaded."""
        return self.model is not None


# Global predictor instance
_predictor = None


def get_predictor() -> GradePredictor:
    """Get the global predictor instance (singleton pattern)."""
    global _predictor
    if _predictor is None:
        _predictor = GradePredictor()
    return _predictor


def predict_grade(
    tfidf_score: float, 
    full_similarity_score: float, 
    mean_structure_similarity: float
) -> Union[str, float]:
    """
    Convenience function to predict grade using the global predictor.
    
    Args:
        tfidf_score: TF-IDF similarity score
        full_similarity_score: Full text embedding similarity score
        mean_structure_similarity: Mean structure similarity score
        
    Returns:
        Predicted grade
    """
    return get_predictor().predict_grade(
        tfidf_score, full_similarity_score, mean_structure_similarity
    )


def get_model_info() -> dict:
    """
    Get information about the loaded model.
    
    Returns:
        Dictionary with model information
    """
    predictor = get_predictor()
    
    info = {
        "model_loaded": predictor.is_model_loaded(),
        "model_path": predictor.model_path,
    }
    
    if predictor.model is not None:
        try:
            # Try to get model type and other info
            info["model_type"] = type(predictor.model).__name__
            
            # Get model parameters if available
            if hasattr(predictor.model, 'get_params'):
                info["model_params"] = predictor.model.get_params()
                
        except Exception as e:
            info["model_info_error"] = str(e)
    
    return info
