from pymongo import MongoClient
from pymongo.errors import PyMongoError

def connect_to_mongodb():
    """
    Connects to MongoDB and lists existing databases
    """
    try:
        uri = "mongodb://localhost:27017/"
        print("📡 Attempting to connect to MongoDB...")

        client = MongoClient(uri)

        dbs = client.list_database_names()
        print("✅ Connected to MongoDB!")
        print("Existing Databases:", dbs)

        return client
    except PyMongoError as e:
        print("❌ MongoDB connection error:")
        print(e)
    except Exception as e:
        print("❌ Unexpected error (MongoDB):")
        print(e)

    return None

def close_mongodb(client):
    """
    Closes the MongoDB client connection
    """
    try:
        if client:
            client.close()
            print("🛑 MongoDB connection closed.")
    except Exception as e:
        print(f"⚠️ Error while closing MongoDB client: {e}")

def main():
    print("=== 🔗 MongoDB Connection Test ===\n")

    client = connect_to_mongodb()

    if client:
        try:
            db = client["grading_system_mongo"]             # Use or create DB
            collection = db["student_results"]        # Use or create collection

            # Insert a test document
            result = collection.insert_one({
                "student": "A001",
                "marks": 87
            })
            print("\n✅ Inserted test document into 'student_results'")
            print(f"Document ID: {result.inserted_id}")

            # List collections
            collections = db.list_collection_names()
            print("\n📂 Collections in 'grading_system':")
            for col in collections:
                print(f"  - {col}")

        except Exception as e:
            print(f"❌ Error during MongoDB operation: {e}")
        finally:
            close_mongodb(client)
    else:
        print("⚠️ MongoDB connection failed.\n")

if __name__ == "__main__":
    main()