"""
Utility functions for the answer key processing pipeline.
Contains common helper functions used across multiple modules.
"""

import logging
import re
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def setup_logging(log_level: int = logging.INFO, log_format: str = '%(asctime)s - %(levelname)s - %(message)s') -> None:
    """Set up logging configuration."""
    logging.basicConfig(level=log_level, format=log_format)


def fix_common_json_issues(json_str: str) -> str:
    """Fix common JSON formatting issues from LLM responses."""
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


def manual_json_parser(text: str) -> Dict[str, Any]:
    """Manually parse malformed JSON text."""
    text = text.strip()
    if text.startswith('{'):
        text = text[1:]
    if text.endswith('}'):
        text = text[:-1]
    
    text = text.strip()
    result = {}
    
    # Replace all variations of double newlines with a standard marker
    cleaned_text = re.sub(r'\n\s*\n', '||SPLIT||', text)
    blocks = cleaned_text.split('||SPLIT||')
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        colon_pos = block.find(':')
        if colon_pos == -1:
            continue
            
        key = block[:colon_pos].strip().strip('"\'').strip()
        value = block[colon_pos+1:].strip()
        
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        
        result[key] = value
    
    return result


def safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON with multiple fallback strategies.
    
    Args:
        text: JSON string to parse
        
    Returns:
        Parsed dictionary or None if all parsing attempts fail
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Try fixing common JSON issues
            fixed_text = fix_common_json_issues(text)
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            try:
                # Try manual parsing as last resort
                result = manual_json_parser(text)
                return result if result else None
            except Exception as e:
                logger.warning(f"All JSON parsing attempts failed: {str(e)}")
                return None


def validate_file_exists(file_path: str) -> bool:
    """Check if a file exists and log appropriate messages."""
    from pathlib import Path
    
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return False
    return True


def ensure_directory_exists(directory_path: str) -> None:
    """Create directory if it doesn't exist."""
    from pathlib import Path
    
    Path(directory_path).mkdir(parents=True, exist_ok=True)


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to specified length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def print_progress(current: int, total: int, prefix: str = "Progress") -> None:
    """Print progress information in a standardized format."""
    percentage = (current / total) * 100 if total > 0 else 0
    print(f"{prefix}: {current}/{total} ({percentage:.1f}%)")
