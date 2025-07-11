import psycopg2
from psycopg2 import OperationalError, Error

def create_tables():
    try:
        # Try connecting to PostgreSQL
        conn = psycopg2.connect(
            dbname="grading_system_pg",
            user="postgres",
            password="root",
            host="localhost",
            port="5432"
        )
        print("✅ Connected to PostgreSQL successfully.")

        cur = conn.cursor()

        # USERS TABLE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
          user_id SERIAL PRIMARY KEY,
          email VARCHAR(100) UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          role VARCHAR(20) NOT NULL DEFAULT 'teacher'
            CHECK (role IN ('teacher', 'admin')),
          created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)

        # COURSE SECTION
        cur.execute("""
        CREATE TABLE IF NOT EXISTS course_section (
          course_id VARCHAR(10) PRIMARY KEY,
          course_name VARCHAR(100) NOT NULL,
          section_id VARCHAR(5),
          teacher_id INT REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)

        # EXAMS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
          exam_id SERIAL PRIMARY KEY,
          exam_type VARCHAR(100) NOT NULL,
          answer_key_file_path TEXT,
          created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)

        # COURSE-EXAM RELATION
        cur.execute("""
        CREATE TABLE IF NOT EXISTS course_exam (
          course_exam_id SERIAL PRIMARY KEY,
          course_id VARCHAR(10) REFERENCES course_section(course_id) ON DELETE CASCADE,
          exam_id INT REFERENCES exams(exam_id) ON DELETE CASCADE,
          UNIQUE(course_id, exam_id)
        );
        """)

        # STUDENTS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
          student_id VARCHAR(50) PRIMARY KEY,
          full_name VARCHAR(100) NOT NULL
        );
        """)

        # STUDENT-COURSE RELATION
        cur.execute("""
        CREATE TABLE IF NOT EXISTS student_course_relation (
          scsr_id SERIAL PRIMARY KEY,
          student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
          course_id VARCHAR(10) REFERENCES course_section(course_id) ON DELETE CASCADE,
          UNIQUE(student_id, course_id)
        );
        """)

        # SUBMISSIONS
        cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
          submission_id UUID PRIMARY KEY,
          course_exam_id INT REFERENCES course_exam(course_exam_id) ON DELETE CASCADE,
          student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
          file_path TEXT,
          status VARCHAR(20) DEFAULT 'uploaded'
            CHECK (status IN ('uploaded', 'processing', 'graded', 'reviewed')),
          is_training_candidate BOOLEAN DEFAULT FALSE,
          UNIQUE(course_exam_id, student_id)
        );
        """)

        # GRADING QUEUE
        cur.execute("""
        CREATE TABLE IF NOT EXISTS grading_queue (
          queue_id SERIAL PRIMARY KEY,
          submission_id UUID REFERENCES submissions(submission_id),
          question_id INT NOT NULL,
          category VARCHAR(100),
          priority INT DEFAULT 0,
          status VARCHAR(20) DEFAULT 'pending'
            CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
          attempt_count INT DEFAULT 0,
          retry_after TIMESTAMPTZ,
          last_updated TIMESTAMPTZ DEFAULT NOW(),
          added_at TIMESTAMPTZ DEFAULT NOW(),
          notes TEXT
        );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ PostgreSQL schema created successfully.")

    except OperationalError as e:
        print("❌ Failed to connect to PostgreSQL:")
        print(e)
    except Error as e:
        print("❌ Error while executing SQL commands:")
        print(e)
    except Exception as e:
        print("❌ Unexpected error occurred:")
        print(e)

# Run it
create_tables()
