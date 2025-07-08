"""
Updated configuration with optional MongoDB support.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Application secrets
SECRET_KEY = os.getenv("SECRET_KEY")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Google OAuth Scopes
SCOPES = [
    "openid", 
    "https://www.googleapis.com/auth/userinfo.email", 
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly", 
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students", 
    "https://www.googleapis.com/auth/classroom.coursework.me",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
    "https://www.googleapis.com/auth/drive.readonly", 
    "https://www.googleapis.com/auth/drive.file"
]

# Google OAuth Client Secrets
CLIENT_SECRETS_FILE = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [GOOGLE_REDIRECT_URI]
    }
}

# Database Configuration
# PostgreSQL Configuration
POSTGRES_USERNAME = os.getenv("POSTGRES_USERNAME", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "root")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "grading_system_pg")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
DATABASE_CONNECT_ARGS = {}

# MongoDB Configuration (Optional)
MONGODB_ENABLED = os.getenv("MONGODB_ENABLED", "false").lower() == "true"
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = os.getenv("MONGODB_PORT", "27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "grading_system_mongo")
MONGODB_URL = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}"

# Session Configuration
SESSION_EXPIRE_DAYS = 7

# File Storage Configuration
SERVER_DATA_DIR = "server_data"
STATIC_DIR = "static"
TEMPLATES_DIR = "templates"

# Grading v1 Engine Configuration (required for backward compatibility)
ANSWER_KEY_FILE = "answer_key.json"
PROCESSED_ANSWER_KEY_FILE = "answer_key_processed.json"
ANSWER_KEY_PRODIGY_FILE = "answer_key_prodigy.jsonl"
STUDENT_ANSWERS_DIR = "student_answers"
PROCESSED_STUDENT_ANSWERS_DIR = "processed_student_answers"
PRODIGY_DATA_DIR = "prodigy_data"
STUDENT_FILE_PATTERN = "*.json"
OUTPUT_FILE_SUFFIX = "_processed.json"
PRODIGY_FILE_SUFFIX = "_prodigy.jsonl"

# Task management for grading
grading_tasks_db = {}
