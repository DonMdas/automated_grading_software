#!/usr/bin/env python3
"""
Simple launcher for the AI Grading Application
"""

import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main launcher function"""
    try:
        # Import uvicorn
        import uvicorn
        
        # Start the server using the module string to ensure lifespan works
        logger.info("🚀 Starting AI Grading Application...")
        logger.info("🌐 Server starting on http://localhost:8000")
        uvicorn.run(
            "app.complete_app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
