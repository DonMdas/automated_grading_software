"""
Unified Database Connector

This module provides a centralized way to connect to both PostgreSQL and MongoDB
using configuration settings. It does not modify any existing app or grading logic.
"""

import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

# SQLAlchemy imports for PostgreSQL
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# PyMongo imports for MongoDB
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

# Configuration
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseConnector:
    """
    Unified database connector for PostgreSQL and MongoDB
    """
    
    def __init__(self):
        self._postgres_engine = None
        self._postgres_session_factory = None
        self._mongo_client = None
        self._mongo_db = None
        
    def initialize_postgres(self) -> bool:
        """
        Initialize PostgreSQL connection using settings from config
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Initializing PostgreSQL connection...")
            
            # Create engine using the DATABASE_URL from settings
            self._postgres_engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=300,    # Recycle connections every 5 minutes
                echo=False           # Set to True for SQL debugging
            )
            
            # Test the connection
            with self._postgres_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create session factory
            self._postgres_session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._postgres_engine
            )
            
            logger.info("✅ PostgreSQL connection initialized successfully")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"❌ PostgreSQL connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error initializing PostgreSQL: {e}")
            return False
    
    def initialize_mongodb(self, database_name: str = "grading_system") -> bool:
        """
        Initialize MongoDB connection using settings from config
        
        Args:
            database_name (str): Name of the MongoDB database to use
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Initializing MongoDB connection...")
            
            # Create MongoDB client using MONGODB_URL from settings
            self._mongo_client = MongoClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Test the connection
            self._mongo_client.admin.command('ping')
            
            # Select database
            self._mongo_db = self._mongo_client[database_name]
            
            logger.info(f"✅ MongoDB connection initialized successfully (database: {database_name})")
            return True
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"❌ MongoDB connection timeout: {e}")
            return False
        except PyMongoError as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error initializing MongoDB: {e}")
            return False
    
    def initialize_all(self, mongo_database_name: str = "grading_system") -> Dict[str, bool]:
        """
        Initialize both PostgreSQL and MongoDB connections
        
        Args:
            mongo_database_name (str): Name of the MongoDB database to use
            
        Returns:
            Dict[str, bool]: Status of each connection attempt
        """
        results = {
            "postgres": self.initialize_postgres(),
            "mongodb": self.initialize_mongodb(mongo_database_name)
        }
        
        if all(results.values()):
            logger.info("🎉 All database connections initialized successfully!")
        else:
            logger.warning(f"⚠️ Some database connections failed: {results}")
            
        return results
    
    @contextmanager
    def get_postgres_session(self):
        """
        Context manager for PostgreSQL sessions
        
        Yields:
            Session: SQLAlchemy session object
        """
        if not self._postgres_session_factory:
            raise RuntimeError("PostgreSQL not initialized. Call initialize_postgres() first.")
        
        session = self._postgres_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_postgres_engine(self):
        """
        Get the PostgreSQL engine
        
        Returns:
            Engine: SQLAlchemy engine object
        """
        if not self._postgres_engine:
            raise RuntimeError("PostgreSQL not initialized. Call initialize_postgres() first.")
        return self._postgres_engine
    
    def get_mongo_database(self) -> Database:
        """
        Get the MongoDB database object
        
        Returns:
            Database: PyMongo database object
        """
        if not self._mongo_db:
            raise RuntimeError("MongoDB not initialized. Call initialize_mongodb() first.")
        return self._mongo_db
    
    def get_mongo_collection(self, collection_name: str) -> Collection:
        """
        Get a MongoDB collection
        
        Args:
            collection_name (str): Name of the collection
            
        Returns:
            Collection: PyMongo collection object
        """
        db = self.get_mongo_database()
        return db[collection_name]
    
    def test_connections(self) -> Dict[str, bool]:
        """
        Test both database connections
        
        Returns:
            Dict[str, bool]: Test results for each database
        """
        results = {}
        
        # Test PostgreSQL
        try:
            if self._postgres_engine:
                with self._postgres_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                results["postgres"] = True
                logger.info("✅ PostgreSQL connection test passed")
            else:
                results["postgres"] = False
                logger.warning("⚠️ PostgreSQL not initialized")
        except Exception as e:
            results["postgres"] = False
            logger.error(f"❌ PostgreSQL connection test failed: {e}")
        
        # Test MongoDB
        try:
            if self._mongo_client:
                self._mongo_client.admin.command('ping')
                results["mongodb"] = True
                logger.info("✅ MongoDB connection test passed")
            else:
                results["mongodb"] = False
                logger.warning("⚠️ MongoDB not initialized")
        except Exception as e:
            results["mongodb"] = False
            logger.error(f"❌ MongoDB connection test failed: {e}")
        
        return results
    
    def close_connections(self):
        """
        Close all database connections
        """
        # Close PostgreSQL
        if self._postgres_engine:
            try:
                self._postgres_engine.dispose()
                logger.info("🛑 PostgreSQL connection closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL connection: {e}")
        
        # Close MongoDB
        if self._mongo_client:
            try:
                self._mongo_client.close()
                logger.info("🛑 MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
        
        # Reset internal state
        self._postgres_engine = None
        self._postgres_session_factory = None
        self._mongo_client = None
        self._mongo_db = None


# Global instance - can be imported and used throughout the application
db_connector = DatabaseConnector()


# Convenience functions for backward compatibility and ease of use
def get_postgres_session():
    """
    Convenience function to get a PostgreSQL session
    """
    return db_connector.get_postgres_session()


def get_mongo_collection(collection_name: str) -> Collection:
    """
    Convenience function to get a MongoDB collection
    
    Args:
        collection_name (str): Name of the collection
        
    Returns:
        Collection: PyMongo collection object
    """
    return db_connector.get_mongo_collection(collection_name)


def get_mongo_database() -> Database:
    """
    Convenience function to get the MongoDB database
    
    Returns:
        Database: PyMongo database object
    """
    return db_connector.get_mongo_database()


# Startup function to initialize connections
def initialize_database_connections(mongo_db_name: str = "grading_system") -> bool:
    """
    Initialize all database connections
    
    Args:
        mongo_db_name (str): Name of the MongoDB database
        
    Returns:
        bool: True if all connections successful, False otherwise
    """
    results = db_connector.initialize_all(mongo_db_name)
    return all(results.values())


# Shutdown function
def close_database_connections():
    """
    Close all database connections
    """
    db_connector.close_connections()


if __name__ == "__main__":
    # Test script when run directly
    logging.basicConfig(level=logging.INFO)
    
    print("=== 🔗 Unified Database Connector Test ===\n")
    
    # Initialize connections
    results = initialize_database_connections()
    
    if results:
        print("🎉 All connections initialized successfully!")
        
        # Test connections
        test_results = db_connector.test_connections()
        print(f"Connection tests: {test_results}")
        
        # Example usage
        try:
            # PostgreSQL example
            with get_postgres_session() as session:
                result = session.execute(text("SELECT 'PostgreSQL is working!' as message"))
                print(f"PostgreSQL test: {result.fetchone()}")
        except Exception as e:
            print(f"PostgreSQL test failed: {e}")
        
        try:
            # MongoDB example
            db = get_mongo_database()
            collection = db["test_collection"]
            test_doc = {"message": "MongoDB is working!", "test": True}
            result = collection.insert_one(test_doc)
            print(f"MongoDB test: Document inserted with ID {result.inserted_id}")
            
            # Clean up test document
            collection.delete_one({"_id": result.inserted_id})
        except Exception as e:
            print(f"MongoDB test failed: {e}")
        
    else:
        print("❌ Some connections failed to initialize")
    
    # Close connections
    close_database_connections()
    print("\n🛑 All connections closed")
