#!/usr/bin/env python3
"""
Startup script for the AI Studio application.
This script handles database initialization and dependency installation.
"""

import subprocess
import sys
import os
from pathlib import Path

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def initialize_databases():
    """Initialize databases"""
    print("🗄️  Initializing databases...")
    try:
        subprocess.check_call([sys.executable, "init_db.py"])
        print("✅ Databases initialized successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to initialize databases: {e}")
        return False

def migrate_data():
    """Migrate data from SQLite if it exists"""
    sqlite_path = Path("app_data.db")
    if sqlite_path.exists():
        print("🔄 Migrating data from SQLite...")
        try:
            subprocess.check_call([sys.executable, "migrate_data.py"])
            print("✅ Data migration completed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to migrate data: {e}")
            return False
    else:
        print("ℹ️  No SQLite database found, skipping migration")
        return True

def start_application():
    """Start the FastAPI application"""
    print("🚀 Starting AI Studio application...")
    try:
        subprocess.check_call([sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start application: {e}")

def main():
    """Main startup function"""
    print("🎓 AI Studio - Automated Grading Platform")
    print("=" * 50)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    # Initialize databases
    if not initialize_databases():
        return False
    
    # Migrate data if needed
    if not migrate_data():
        return False
    
    print("\n✅ Startup completed successfully!")
    
    # Get the application URL from environment or use default
    app_port = os.getenv("APP_PORT", "8000")
    domain = os.getenv("DOMAIN", "localhost")
    protocol = "https" if os.getenv("SSL_CERT_PATH") else "http"
    app_url = f"{protocol}://{domain}:{app_port}"
    
    print(f"🌐 Application will be available at: {app_url}")
    print(f"📚 API documentation: {app_url}/docs")
    print("\nPress Ctrl+C to stop the application")
    print("-" * 50)
    
    # Start the application
    start_application()
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
