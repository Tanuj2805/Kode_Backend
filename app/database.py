from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import asyncio

client = None
db = None

async def connect_db():
    global client, db
    try:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        await client.admin.command('ping')
        db = client.get_database()
        print(f"Connected to MongoDB: {settings.mongodb_uri}")
    except Exception as e:
        print(f"WARNING: MongoDB not available: {e}")
        print("Guest mode will work without MongoDB!")
        client = None
        db = None

async def close_db():
    global client
    if client:
        try:
            client.close()
            print("MongoDB connection closed")
        except:
            pass

def get_database():
    if db is None:
        raise Exception("MongoDB not connected. Please install and start MongoDB for this feature.")
    return db

def get_database_optional():
    """Returns database if connected, None otherwise (for optional features)"""
    return db

def is_database_connected():
    """Check if database is connected"""
    return db is not None

