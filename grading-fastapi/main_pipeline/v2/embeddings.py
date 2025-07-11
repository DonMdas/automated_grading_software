"""
BERT embedding utilities for text processing.
"""

import torch
from transformers import BertTokenizer, BertModel
import logging
from .config import BERT_MODEL_NAME, EMBEDDING_DIMENSION, MAX_SEQUENCE_LENGTH

logger = logging.getLogger(__name__)

class BERTEmbedder:
    """Class to handle BERT embedding generation"""
    
    def __init__(self):
        """Initialize BERT model and tokenizer"""
        try:
            self.tokenizer = BertTokenizer.from_pretrained(BERT_MODEL_NAME)
            self.model = BertModel.from_pretrained(BERT_MODEL_NAME)
            logger.info("BERT model and tokenizer loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load BERT model: {str(e)}")
            raise e
    
    def get_mean_pooled_embedding(self, text):
        """Generate mean-pooled BERT embeddings for text"""
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

# Global embedder instance
_embedder = None

def get_embedder():
    """Get or create global embedder instance"""
    global _embedder
    if _embedder is None:
        _embedder = BERTEmbedder()
    return _embedder

def get_mean_pooled_embedding(text):
    """Convenience function for getting embeddings"""
    return get_embedder().get_mean_pooled_embedding(text)
