"""
Quick script to make a user an admin
Usage: python make_admin.py your@email.com
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def make_admin(email):
    """Make a user admin by email"""
    
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/compiler")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.get_database()
    
    try:
        await client.admin.command('ping')
        print(f"✅ Connected to MongoDB")
        
        # Find user
        user = await db.users.find_one({"email": email})
        print(user)
        #exit()
        #exit
        if not user:
            print(f"❌ User with email '{email}' not found")
            print(f"\n📋 Available users:")
            users = await db.users.find({}, {"email": 1, "username": 1}).to_list(length=100)
            for u in users:
                is_admin = u.get("is_admin", False)
                status = "👨‍💼 ADMIN" if is_admin else "👤 USER"
                print(f"  - {u['email']} ({u['username']}) {status}")
            return
        
        # Check if already admin
        if user.get("is_admin", False):
            print(f"ℹ️  {email} is already an admin")
        else:
            # Make admin
            await db.users.update_one(
                {"email": email},
                {"$set": {"is_admin": True}}
            )
            print(f"✅ Made {email} an admin!")
        
        print(f"\n👨‍💼 User Details:")
        print(f"  Email: {user['email']}")
        print(f"  Username: {user['username']}")
        print(f"  Admin: {user.get('is_admin', False)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py your@email.com")
        print("\nOr run without arguments to list all users:")
        asyncio.run(make_admin(""))
    else:
        email = sys.argv[1]
        asyncio.run(make_admin(email))











