# db_tools.py

import pymongo
from datetime import datetime

# --- MongoDB Configuration ---
# Use a global client variable or a connection pool for efficiency 
# (though for a simple script, initializing here is fine, but close it cleanly).
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "AgenticInsuranceDB"
COLLECTION_NAME = "PolicyDecisions"

def record_underwriting_decision(application_id: str, decision: str, notes: str) -> str:
    """
    Writes the final underwriting decision to MongoDB. This function is
    designed to be used as an AutoGen tool and returns a simple string 
    confirmation or error message.

    Args:
        application_id (str): Unique application ID (e.g., APP-1003).
        decision (str): Decision string (e.g., 'DECLINED').
        notes (str): Notes explaining the decision.

    Returns:
        str: A simple string message confirming the result for the agent 
             to parse and use for termination.
    """
    
    # 1. Input Validation
    if not all([application_id, decision, notes]):
        # This message will be sent to the LLM
        return "ERROR: Missing required fields (application_id, decision, or notes) for MongoDB write."

    print("--- ATTEMPTING MONGODB WRITE ---") 
    
    # Use a 'with' statement for client to ensure connection closes gracefully
    try:
        with pymongo.MongoClient(MONGO_URI) as client:
            db = client[DATABASE_NAME]
            collection = db[COLLECTION_NAME]

            # 2. Prepare the document
            decision_document = {
                # _id is typically preferred for unique keys
                "_id": application_id,
                "application_id": application_id,
                "decision": decision,
                "notes": notes,
                "timestamp": datetime.utcnow().isoformat()
            }

            # 3. Write to MongoDB (Use upsert=True to insert or update)
            result = collection.update_one(
                {"_id": application_id},
                {"$set": decision_document},
                upsert=True
            )

            # 4. Generate confirmation message
            status = 'Inserted' if result.upserted_id else 'Modified'
            print(f"DEBUG: MongoDB Upsert Status: {status} | ID: {application_id}")
            
            # CRUCIAL: Return a simple, consistent success message 
            # for the LLM to parse and the UserProxyAgent to echo.
            return f"Underwriting decision successfully recorded for {application_id}. Status: {status}. **Decision recorded**"

    except pymongo.errors.ConnectionError:
        # Specific error handling for connection issues
        error_msg = f"DB_ERROR: Could not connect to MongoDB at {MONGO_URI}. Is the server running?"
        print(error_msg)
        return error_msg
        
    except Exception as e:
        # General error handling
        error_msg = f"DB_ERROR: An unexpected error occurred during write. Error: {str(e)}"
        print(error_msg)
        return error_msg