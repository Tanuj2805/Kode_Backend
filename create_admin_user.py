import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin_user(email, username, password):
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/compiler")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.get_database()
    
    try:
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
        
        # Check if user already exists
        existing = await db.users.find_one({"email": email})
        if existing:
            print(f"⚠️  User with email {email} already exists!")
            
            # Just make them admin
            await db.users.update_one(
                {"email": email},
                {"$set": {"is_admin": True}}
            )
            print(f"✅ Made {email} an admin!")
        else:
            # Create new user
            hashed_password = pwd_context.hash(password)
            
            user_doc = {
                "username": username,
                "email": email,
                "password": hashed_password,
                "is_admin": True,
                "created_at": datetime.utcnow(),
                "total_points": 0,
                "solved_problems": []
            }
            
            result = await db.users.insert_one(user_doc)
            print(f"✅ Created new admin user: {email}")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            print(f"   Admin: Yes")
        
        print(f"\n🎉 You can now login at http://localhost:3000/login")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    email = "amanadeshrivastava@gmail.com"
    username = "admin"
    password = "admin123"
    
    asyncio.run(create_admin_user(email, username, password))










