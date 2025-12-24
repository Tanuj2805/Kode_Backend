import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

async def activate_all_problems():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client.get_database()
    
    try:
        await client.admin.command('ping')
        print("✅ Connected to MongoDB\n")
        
        # Find all draft problems
        drafts = await db.problems.find({"status": "draft"}).to_list(length=100)
        
        print(f"📋 Found {len(drafts)} draft problem(s):\n")
        for p in drafts:
            print(f"   - #{p['problem_id']}: {p['title']}")
        
        if len(drafts) == 0:
            print("No draft problems to activate!")
            return
        
        print()
        response = input("Activate ALL these problems? (yes/no): ")
        
        if response.lower() in ['yes', 'y']:
            result = await db.problems.update_many(
                {"status": "draft"},
                {"$set": {"status": "active"}}
            )
            print(f"\n✅ Activated {result.modified_count} problem(s)!")
            print(f"\n🎉 Go to http://localhost:3000/problems to see them!")
        else:
            print("\nCancelled.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(activate_all_problems())










