import os
from decouple import config

class Settings:
    PROJECT_NAME = "AI Automated Grading Platform"
    PROJECT_VERSION = "1.0.0"
    
    # Database
    DATABASE_URL = config("DATABASE_URL", default="sqlite:///./grading_platform.db")
    MONGODB_URL = config("MONGODB_URL", default="mongodb://localhost:27017")
    
    # Security
    SECRET_KEY = config("SECRET_KEY", default="your-secret-key-here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    
    # OCR Settings
    TESSERACT_CMD = config("TESSERACT_CMD", default="/usr/bin/tesseract")
    
    # Google Classroom
    GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
    GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
    GOOGLE_REDIRECT_URI = config("GOOGLE_REDIRECT_URI", default="http://localhost:8000/api/classroom/auth/callback")
    GOOGLE_CLIENT_SECRETS_FILE = config("GOOGLE_CLIENT_SECRETS_FILE", default="client_secrets.json")
    
    # File Upload
    UPLOAD_DIR = "uploads"
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Redis
    REDIS_URL = config("REDIS_URL", default="redis://localhost:6379")

settings = Settings()
