#!/usr/bin/env python3
"""
Database initialization script for the AI Studio application.
This script creates the necessary tables in PostgreSQL and collections in MongoDB.
"""

import sys
import os
from sqlalchemy.exc import OperationalError
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import initialize_databases, engine, mongodb_client
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE

def test_postgresql_connection():
    """Test PostgreSQL connection"""
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            print(f"✅ PostgreSQL connection successful!")
            print(f"   Host: {POSTGRES_HOST}:{POSTGRES_PORT}")
            print(f"   Database: {POSTGRES_DATABASE}")
            return True
    except OperationalError as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print(f"   Host: {POSTGRES_HOST}:{POSTGRES_PORT}")
        print(f"   Database: {POSTGRES_DATABASE}")
        return False

def test_mongodb_connection():
    """Test MongoDB connection"""
    try:
        # The ismaster command is cheap and does not require auth.
        mongodb_client.admin.command('ismaster')
        print(f"✅ MongoDB connection successful!")
        print(f"   Host: {MONGODB_HOST}:{MONGODB_PORT}")
        print(f"   Database: {MONGODB_DATABASE}")
        return True
    except (ServerSelectionTimeoutError, ConnectionFailure) as e:
        print(f"❌ MongoDB connection failed: {e}")
        print(f"   Host: {MONGODB_HOST}:{MONGODB_PORT}")
        print(f"   Database: {MONGODB_DATABASE}")
        return False

def main():
    """Main function to initialize databases"""
    print("🚀 Initializing AI Studio Databases...")
    print("=" * 50)
    
    # Test connections first
    print("\n📡 Testing database connections...")
    pg_ok = test_postgresql_connection()
    mongo_ok = test_mongodb_connection()
    
    if not pg_ok:
        print("\n❌ PostgreSQL connection failed. Please check:")
        print("   - PostgreSQL is running")
        print("   - Database credentials are correct")
        print("   - Database exists")
        return False
    
    if not mongo_ok:
        print("\n❌ MongoDB connection failed. Please check:")
        print("   - MongoDB is running")
        print("   - Connection parameters are correct")
        return False
    
    print("\n🔧 Creating database schema...")
    
    try:
        initialize_databases()
        print("\n✅ Database initialization completed successfully!")
        print("\nDatabase schema created:")
        print("📊 PostgreSQL Tables:")
        print("   - users (with UUID primary keys)")
        print("   - user_sessions")
        print("   - courses")
        print("   - assignments")
        print("   - students")
        print("   - exams")
        print("   - submissions")
        print("   - grading_tasks")
        print("\n📄 MongoDB Collections:")
        print("   - answer_keys")
        print("   - student_answers")
        print("   - grading_results")
        print("   - grade_edits")
        print("   - training_data")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
