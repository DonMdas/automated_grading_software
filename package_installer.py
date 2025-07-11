"""
Dynamic package installer utility.
This module provides functions to install missing packages at runtime
without rebuilding the entire Docker image.
"""

import subprocess
import sys
import importlib
import logging
from typing import List, Union

logger = logging.getLogger(__name__)

def install_package(package: str) -> bool:
    """
    Install a package using pip.
    
    Args:
        package (str): The package name to install (e.g., 'srsly>=2.5.1')
        
    Returns:
        bool: True if installation successful, False otherwise
    """
    try:
        logger.info(f"Installing package: {package}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package}: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error installing {package}: {e}")
        return False

def check_and_install_package(package_name: str, install_name: str = None) -> bool:
    """
    Check if a package is available, install it if not.
    
    Args:
        package_name (str): The name used for importing (e.g., 'srsly')
        install_name (str): The name used for pip install (e.g., 'srsly>=2.5.1').
                          If None, uses package_name.
                          
    Returns:
        bool: True if package is available (either already installed or successfully installed)
    """
    if install_name is None:
        install_name = package_name
        
    try:
        importlib.import_module(package_name)
        logger.debug(f"Package {package_name} is already available")
        return True
    except ImportError:
        logger.warning(f"Package {package_name} not found, attempting to install...")
        return install_package(install_name)

def ensure_packages(packages: List[Union[str, tuple]]) -> bool:
    """
    Ensure multiple packages are available, installing them if necessary.
    
    Args:
        packages: List of packages. Each item can be:
                 - str: package name (used for both import and install)
                 - tuple: (import_name, install_name)
                 
    Returns:
        bool: True if all packages are available
    """
    all_success = True
    
    for package in packages:
        if isinstance(package, tuple):
            import_name, install_name = package
        else:
            import_name = install_name = package
            
        if not check_and_install_package(import_name, install_name):
            all_success = False
            
    return all_success

# Common packages that might be missing
COMMON_MISSING_PACKAGES = [
    ("srsly", "srsly>=2.5.1"),
    ("spacy", "spacy>=3.4.0"),
    ("nltk", "nltk"),
    ("textstat", "textstat"),
    ("sentence_transformers", "sentence-transformers"),
]

def check_grading_dependencies() -> bool:
    """
    Check and install common grading pipeline dependencies.
    
    Returns:
        bool: True if all dependencies are available
    """
    logger.info("Checking grading pipeline dependencies...")
    
    # Essential packages for grading pipeline
    required_packages = [
        ("srsly", "srsly>=2.5.1"),
        ("pandas", "pandas"),
        ("numpy", "numpy"),
        ("sklearn", "scikit-learn"),
    ]
    
    return ensure_packages(required_packages)
