"""
Database Migration Script
Updates the student table to allow students in multiple courses.
This removes the unique constraint on google_student_id and adds a composite unique constraint.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from config import SQLALCHEMY_DATABASE_URL, DATABASE_CONNECT_ARGS

def migrate_database():
    """
    Migrate the database to support students in multiple courses.
    """
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=DATABASE_CONNECT_ARGS)
    
    print("Starting database migration...")
    
    with engine.connect() as conn:
        try:
            # Start a transaction
            trans = conn.begin()
            
            print("1. Dropping existing unique constraint on google_student_id...")
            
            # Drop the existing unique constraint
            try:
                conn.execute(text("ALTER TABLE students DROP CONSTRAINT IF EXISTS students_google_student_id_key"))
                print("   ✓ Dropped unique constraint on google_student_id")
            except Exception as e:
                print(f"   ⚠ Warning: Could not drop constraint (may not exist): {e}")
            
            # Drop the existing unique index if it exists
            try:
                conn.execute(text("DROP INDEX IF EXISTS ix_students_google_student_id"))
                print("   ✓ Dropped unique index on google_student_id")
            except Exception as e:
                print(f"   ⚠ Warning: Could not drop index (may not exist): {e}")
            
            print("2. Creating new composite unique constraint...")
            
            # Create the new composite unique constraint
            try:
                conn.execute(text("ALTER TABLE students ADD CONSTRAINT unique_student_per_course UNIQUE (google_student_id, course_id)"))
                print("   ✓ Created unique constraint on (google_student_id, course_id)")
            except Exception as e:
                print(f"   ⚠ Warning: Could not create constraint (may already exist): {e}")
            
            # Create a regular index on google_student_id for performance
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_students_google_student_id ON students (google_student_id)"))
                print("   ✓ Created index on google_student_id")
            except Exception as e:
                print(f"   ⚠ Warning: Could not create index: {e}")
            
            print("3. Checking for duplicate students...")
            
            # Check for any duplicate students that might cause issues
            result = conn.execute(text("""
                SELECT google_student_id, COUNT(*) as count
                FROM students 
                GROUP BY google_student_id 
                HAVING COUNT(*) > 1
            """)).fetchall()
            
            if result:
                print(f"   ⚠ Warning: Found {len(result)} students with duplicate google_student_ids:")
                for row in result:
                    print(f"     - Student ID: {row[0]}, Count: {row[1]}")
                print("   These students can now exist in multiple courses.")
            else:
                print("   ✓ No duplicate students found")
            
            # Commit the transaction
            trans.commit()
            print("✅ Database migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {e}")
            raise
        
        finally:
            conn.close()

if __name__ == "__main__":
    migrate_database()
