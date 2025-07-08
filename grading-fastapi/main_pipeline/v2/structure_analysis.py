"""
Structure analysis and parsing utilities for answer processing.
"""

import json
import re
import logging
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .llm_prompting import invoke_llm
from .config import LLM_MODELS, MAX_STRUCTURE_COMPONENTS, MIN_CONTENT_LENGTH

logger = logging.getLogger(__name__)

def fix_common_json_issues(json_str):
    """Fix common JSON formatting issues from LLM responses"""
    # Replace unquoted property names with quoted ones
    fixed = re.sub(r'([{,])\s*(\w+)\s*:', r'\1 "\2":', json_str)
    
    # Replace single quotes with double quotes
    fixed = fixed.replace("'", '"')
    
    # Fix missing commas between properties
    fixed = re.sub(r'(")(\s*\n\s*")(\w+)(":\s*")', r'\1,\2\3\4', fixed)
    fixed = re.sub(r'(")(\s*\n\s*\n\s*")(\w+)(":\s*)', r'\1,\2\3\4', fixed)
    
    # Fix trailing commas
    fixed = re.sub(r',\s*}', '}', fixed)
    fixed = re.sub(r',\s*]', ']', fixed)
    
    return fixed

def manual_json_parser(text):
    """Manually parse malformed JSON text, including JSON wrapped in code blocks"""
    text = text.strip()
    
    # Remove code block markers if present
    if text.startswith('```json'):
        text = text[7:]  # Remove ```json
    elif text.startswith('```'):
        text = text[3:]   # Remove ```
    
    if text.endswith('```'):
        text = text[:-3]  # Remove closing ```
    
    text = text.strip()
    
    # If it's properly formatted JSON, try parsing it first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # For the new format, we expect a proper JSON structure
    # Try to fix common issues and parse again
    try:
        fixed_text = fix_common_json_issues(text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass
    
    # If still failing, return empty structure
    logger.error(f"Could not parse JSON structure from: {text[:200]}...")
    return {"breakdown": {}, "requires_llm_evaluation": []}

def simple_structure_fallback(answer_text):
    """
    Simple fallback structure parser when LLM is unavailable.
    Splits answer into logical components based on common patterns.
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
        for i, part in enumerate(parts[:MAX_STRUCTURE_COMPONENTS]):  # Limit to max components
            if len(part) > MIN_CONTENT_LENGTH:  # Only include substantial parts
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

def infer_answer_structure(answer_text, use_fallback=True):
    """Infer structure of an answer using LLM with fallback option"""
    try:
        response = invoke_llm(LLM_MODELS["breakdown_model"], str(answer_text))
        
        # Try parsing the response
        try:
            parsed_response = json.loads(response)
            # Validate the new format
            if isinstance(parsed_response, dict) and "breakdown" in parsed_response:
                if "requires_llm_evaluation" not in parsed_response:
                    parsed_response["requires_llm_evaluation"] = []
                return parsed_response
            else:
                # Old format or invalid, try manual parsing
                raise ValueError("Invalid response format")
        except json.JSONDecodeError:
            # Try fixing common JSON issues
            try:
                fixed_response = fix_common_json_issues(response)
                parsed_response = json.loads(fixed_response)
                if isinstance(parsed_response, dict) and "breakdown" in parsed_response:
                    if "requires_llm_evaluation" not in parsed_response:
                        parsed_response["requires_llm_evaluation"] = []
                    return parsed_response
                else:
                    raise ValueError("Invalid response format after fixing")
            except json.JSONDecodeError:
                # Try manual parsing as last resort
                try:
                    result = manual_json_parser(response)
                    if result and "breakdown" in result:
                        if "requires_llm_evaluation" not in result:
                            result["requires_llm_evaluation"] = []
                        return result
                    else:
                        raise ValueError("Manual parser failed to return valid structure")
                except Exception as e:
                    if use_fallback:
                        logger.warning(f"LLM parsing failed, using simple fallback: {str(e)}")
                        fallback_structure = simple_structure_fallback(answer_text)
                        return {"breakdown": fallback_structure, "requires_llm_evaluation": []}
                    else:
                        logger.error(f"Failed to parse LLM response: {str(e)}")
                        return {"error": f"Failed to parse LLM response: {str(e)}", "raw_response": response}
    except Exception as e:
        if "memory" in str(e).lower() or "500" in str(e):
            if use_fallback:
                logger.warning(f"LLM memory issue, using simple fallback: {str(e)}")
                fallback_structure = simple_structure_fallback(answer_text)
                return {"breakdown": fallback_structure, "requires_llm_evaluation": []}
            else:
                logger.error(f"LLM memory error: {str(e)}")
                return {"error": f"LLM memory error: {str(e)}"}
        else:
            logger.error(f"Error in structure inference: {str(e)}")
            return {"error": f"Error in LLM processing: {str(e)}"}

def map_student_to_answer_key_structure(answer_key_structure, full_student_text):
    """
    Map student answer structure components to answer key structure components.
    Uses simple text matching and LLM mapping when available.
    """
    try:
        # Create structure mapping prompt
        ak_keys = list(answer_key_structure.keys())
        prompt = str({
            "answer_key_structure": ak_keys,
            "student_answer_text": full_student_text
        })
        
        response = invoke_llm(LLM_MODELS["structure_mapper"], prompt)
        mapping_result = manual_json_parser(response)
        
        # Validate and return mapping
        if isinstance(mapping_result, dict):
            return mapping_result
    except Exception as e:
        logger.debug(f"LLM mapping failed: {str(e)}")
        return {}
