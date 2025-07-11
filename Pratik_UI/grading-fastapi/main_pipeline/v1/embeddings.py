"""
BERT embedding functionality for text processing.
Handles loading BERT model and generating embeddings.
"""

import torch
import logging
import sys
from typing import List, Optional
from transformers import BertTokenizer, BertModel

from .config import BERT_MODEL_NAME, EMBEDDING_DIMENSION, MAX_SEQUENCE_LENGTH

logger = logging.getLogger(__name__)


class BERTEmbedder:
    """Class to handle BERT model loading and embedding generation."""
    
    def __init__(self, model_name: str = BERT_MODEL_NAME):
        """
        Initialize BERT model and tokenizer.
        
        Args:
            model_name: Name of the BERT model to load
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self._load_model()
    
    def _load_model(self) -> None:
        """Load BERT model and tokenizer."""
        try:
            self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
            self.model = BertModel.from_pretrained(self.model_name)
            logger.info(f"BERT model '{self.model_name}' loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load BERT model '{self.model_name}': {str(e)}")
            sys.exit(1)
    
    def get_mean_pooled_embedding(self, text: str) -> List[float]:
        """
        Generate mean-pooled BERT embeddings for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding
        """
        try:
            if not isinstance(text, str):
                text = str(text)
            if not text.strip():
                text = " "
                
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                padding=True, 
                max_length=MAX_SEQUENCE_LENGTH
            )
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            last_hidden_state = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"]
            mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
            summed = torch.sum(last_hidden_state * mask, dim=1)
            counted = torch.clamp(mask.sum(dim=1), min=1e-9)
            mean_pooled = summed / counted
            return mean_pooled.squeeze().tolist()
            
        except Exception as e:
            logger.error(f"Embedding failed for text: {e}")
            return [0.0] * EMBEDDING_DIMENSION
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings
        """
        embeddings = []
        for text in texts:
            embeddings.append(self.get_mean_pooled_embedding(text))
        return embeddings


# Global embedder instance
_embedder: Optional[BERTEmbedder] = None


def get_embedder() -> BERTEmbedder:
    """Get the global embedder instance (singleton pattern)."""
    global _embedder
    if _embedder is None:
        _embedder = BERTEmbedder()
    return _embedder


def get_mean_pooled_embedding(text: str) -> List[float]:
    """
    Convenience function to get embedding using the global embedder.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of floats representing the embedding
    """
    return get_embedder().get_mean_pooled_embedding(text)
