"""
Structure analysis and inference functionality.
Handles structure parsing, LLM-based inference, and fallback mechanisms.
"""

import re
import json
import logging
import sys
import os
from typing import Dict, Any, Optional

from .utils import safe_json_parse
from .config import LLM_MODELS, MAX_STRUCTURE_COMPONENTS, MIN_COMPONENT_LENGTH

# Add parent directory to path to import LLM module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from llm_prompting import invoke_llm
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("LLM prompting module not available")
    invoke_llm = None

logger = logging.getLogger(__name__)


def simple_structure_fallback(answer_text: str) -> Dict[str, str]:
    """
    Simple fallback structure parser when LLM is unavailable.
    Splits answer into logical components based on common patterns.
    
    Args:
        answer_text: Text to analyze
        
    Returns:
        Dictionary with structure components
    """
    try:
        # Clean the text
        text = answer_text.strip()
        
        # Common patterns to split on
        patterns = [
            r'\n\n+',  # Double newlines
            r'\n\([i-z]\)',  # (i), (ii), etc.
            r'\n[0-9]+\.',  # 1., 2., etc.
            r'\n[A-Z][a-z]+:',  # Word: patterns
            r'\n- ',  # Bullet points
        ]
        
        parts = [text]
        for pattern in patterns:
            new_parts = []
            for part in parts:
                split_parts = re.split(pattern, part)
                new_parts.extend([p.strip() for p in split_parts if p.strip()])
            parts = new_parts
        
        # Create structure dictionary
        structure = {}
        for i, part in enumerate(parts[:MAX_STRUCTURE_COMPONENTS]):
            if len(part) > MIN_COMPONENT_LENGTH:  # Only include substantial parts
                key = f"component_{i+1}"
                structure[key] = part
        
        # If no clear structure found, create sections
        if len(structure) <= 1:
            sentences = text.split('. ')
            mid_point = len(sentences) // 2
            
            structure = {
                "introduction": '. '.join(sentences[:mid_point]) + '.',
                "main_content": '. '.join(sentences[mid_point:])
            }
        
        return structure
        
    except Exception as e:
        logger.warning(f"Simple structure fallback failed: {str(e)}")
        return {"full_answer": answer_text}


def infer_answer_structure(
    answer_text: str, 
    model_name: str = "breakdown_model", 
    use_fallback: bool = True
) -> Dict[str, Any]:
    """
    Infer structure of an answer using LLM with fallback option.
    
    Args:
        answer_text: Text to analyze
        model_name: LLM model to use for structure inference
        use_fallback: Whether to use simple fallback when LLM fails
        
    Returns:
        Dictionary with inferred structure
    """
    if invoke_llm is None:
        if use_fallback:
            logger.warning("LLM not available, using simple fallback")
            return simple_structure_fallback(answer_text)
        else:
            return {"error": "LLM not available and fallback disabled"}
    
    try:
        # Get LLM model name from config
        llm_model = LLM_MODELS.get(model_name, model_name)
        response = invoke_llm(llm_model, str(answer_text))
        
        # Try parsing the response
        parsed_response = safe_json_parse(response)
        
        if parsed_response is not None:
            return parsed_response
        else:
            if use_fallback:
                logger.warning("LLM parsing failed, using simple fallback")
                return simple_structure_fallback(answer_text)
            else:
                logger.error("Failed to parse LLM response")
                return {
                    "error": "Failed to parse LLM response", 
                    "raw_response": response
                }
                
    except Exception as e:
        if "memory" in str(e).lower() or "500" in str(e):
            if use_fallback:
                logger.warning(f"LLM memory issue, using simple fallback: {str(e)}")
                return simple_structure_fallback(answer_text)
            else:
                logger.error(f"LLM memory error: {str(e)}")
                return {"error": f"LLM memory error: {str(e)}"}
        else:
            logger.error(f"Error in structure inference: {str(e)}")
            return {"error": f"Error in LLM processing: {str(e)}"}


def map_student_to_answer_key_structure(
    student_structure: Dict[str, str], 
    answer_key_structure: Dict[str, Any], 
    full_student_text: str
) -> Dict[str, str]:
    """
    Map student answer structure components to answer key structure components.
    Uses LLM mapping when available, with simple fallback strategies.
    
    Args:
        student_structure: Student answer structure components
        answer_key_structure: Answer key structure components
        full_student_text: Full student answer text for fallback
        
    Returns:
        Mapped structure dictionary
    """
    try:
        # First, try LLM-based mapping if available
        if (invoke_llm is not None and 
            len(student_structure) > 1 and 
            len(answer_key_structure) > 1):
            try:
                # Create structure mapping prompt
                ak_keys = list(answer_key_structure.keys())
                student_keys = list(student_structure.keys())
                
                prompt = f"""Map the student answer structure to the answer key structure.
Answer key structure: {ak_keys}
Student structure: {student_keys}
Student answer: {full_student_text[:500]}...

Return a JSON mapping where keys are answer key structure names and values are the corresponding student structure content."""
                
                llm_model = LLM_MODELS.get("structure_mapper", "structure_mapper")
                response = invoke_llm(llm_model, prompt)
                mapping_result = safe_json_parse(response)
                
                # Validate and return mapping
                if mapping_result is not None and isinstance(mapping_result, dict):
                    return mapping_result
                    
            except Exception as e:
                logger.debug(f"LLM mapping failed, using fallback: {str(e)}")
        
        # Fallback: Simple mapping strategy
        mapped_structure = {}
        ak_keys = list(answer_key_structure.keys())
        student_keys = list(student_structure.keys())
        
        # If same number of components, map by order
        if len(ak_keys) == len(student_keys):
            for i, ak_key in enumerate(ak_keys):
                if i < len(student_keys):
                    mapped_structure[ak_key] = student_structure[student_keys[i]]
        else:
            # If different numbers, try to map the first few
            for i, ak_key in enumerate(ak_keys):
                if i < len(student_keys):
                    mapped_structure[ak_key] = student_structure[student_keys[i]]
                else:
                    # Use remaining text or full text for unmatched components
                    mapped_structure[ak_key] = full_student_text
        
        return mapped_structure
        
    except Exception as e:
        logger.warning(f"Error in structure mapping: {str(e)}")
        # Emergency fallback: map everything to full text
        return {key: full_student_text for key in answer_key_structure.keys()}


def validate_structure(structure: Dict[str, Any]) -> bool:
    """
    Validate that a structure dictionary is properly formatted.
    
    Args:
        structure: Structure dictionary to validate
        
    Returns:
        True if structure is valid, False otherwise
    """
    if not isinstance(structure, dict):
        return False
    
    if "error" in structure:
        return False
    
    if len(structure) == 0:
        return False
    
    # Check that all values are strings or dicts with content
    for key, value in structure.items():
        if isinstance(value, str):
            if not value.strip():
                return False
        elif isinstance(value, dict):
            if "content" not in value:
                return False
        else:
            return False
    
    return True
