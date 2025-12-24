"""
Setup script for dynamic problem management system
This script will:
1. Create database indexes
2. Add sample problems to MongoDB
3. Set an admin user
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Sample problem data
SAMPLE_PROBLEMS = [
    {
        "problem_id": 1,
        "title": "Two Sum",
        "difficulty": "Easy",
        "category": "Arrays",
        "description": """Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.

You may assume that each input would have exactly one solution, and you may not use the same element twice.

You can return the answer in any order.

Example 1:
Input: nums = [2,7,11,15], target = 9
Output: [0,1]
Explanation: Because nums[0] + nums[1] == 9, we return [0, 1].

Example 2:
Input: nums = [3,2,4], target = 6
Output: [1,2]

Example 3:
Input: nums = [3,3], target = 6
Output: [0,1]""",
        "examples": [
            {"input": "nums = [2,7,11,15], target = 9", "output": "[0,1]", "explanation": "Because nums[0] + nums[1] == 9, we return [0, 1]."},
            {"input": "nums = [3,2,4], target = 6", "output": "[1,2]", "explanation": "nums[1] + nums[2] == 6"},
            {"input": "nums = [3,3], target = 6", "output": "[0,1]", "explanation": "nums[0] + nums[1] == 6"}
        ],
        "constraints": [
            "2 <= nums.length <= 10⁴",
            "-10⁹ <= nums[i] <= 10⁹",
            "-10⁹ <= target <= 10⁹",
            "Only one valid answer exists."
        ],
        "input_format": "Line 1: JSON array of numbers\\nLine 2: Target integer",
        "output_format": "Array of two indices [i, j]",
        "sample_test_case": {
            "input": "[2,7,11,15]\\n9",
            "expected": "[0, 1]"
        },
        "starter_code": {
            "python": """def two_sum(nums, target):
    \"\"\"
    Find two numbers that add up to target
    :type nums: List[int]
    :type target: int
    :rtype: List[int]
    
    Write your code below - input/output is handled automatically
    \"\"\"
    # Your solution here
    pass

# Automatic input/output handling - DO NOT MODIFY
if __name__ == "__main__":
    import json
    try:
        nums = json.loads(input())
        target = int(input())
        result = two_sum(nums, target)
        print(result)
    except:
        print([])""",
            "javascript": """/**
 * @param {number[]} nums
 * @param {number} target
 * @return {number[]}
 */
function twoSum(nums, target) {
    // Write your solution here
}

// Test
console.log(twoSum([2, 7, 11, 15], 9));  // Expected: [0, 1]""",
            "java": """class Solution {
    public int[] twoSum(int[] nums, int target) {
        // Write your solution here
        return new int[0];
    }
    
    public static void main(String[] args) {
        Solution sol = new Solution();
        int[] result = sol.twoSum(new int[]{2, 7, 11, 15}, 9);
        System.out.println("[" + result[0] + ", " + result[1] + "]");
    }
}""",
            "cpp": """#include <iostream>
#include <vector>
using namespace std;

vector<int> twoSum(vector<int>& nums, int target) {
    // Write your solution here
    return {};
}

int main() {
    vector<int> nums = {2, 7, 11, 15};
    int target = 9;
    vector<int> result = twoSum(nums, target);
    cout << "[" << result[0] << ", " << result[1] << "]" << endl;
    return 0;
}""",
            "go": """package main
import "fmt"

func twoSum(nums []int, target int) []int {
    // Write your solution here
    return []int{}
}

func main() {
    nums := []int{2, 7, 11, 15}
    target := 9
    fmt.Println(twoSum(nums, target))
}"""
        },
        "hints": [
            "A really brute force way would be to search for all possible pairs of numbers but that would be too slow.",
            "Use a hash table to store the numbers you've seen so far.",
            "For each number, check if target - number exists in the hash table."
        ],
        "test_cases": [
            {"input": "[2,7,11,15]\\n9", "expected": "[0, 1]", "hidden": False},
            {"input": "[3,2,4]\\n6", "expected": "[1, 2]", "hidden": False},
            {"input": "[3,3]\\n6", "expected": "[0, 1]", "hidden": False},
            {"input": "[1,5,3,7,9]\\n12", "expected": "[2, 4]", "hidden": True},
            {"input": "[-1,-2,-3,-4,-5]\\n-8", "expected": "[2, 4]", "hidden": True}
        ],
        "time_limit": 5000,
        "memory_limit": 128000,
        "points": 100,
        "tags": ["array", "hash-table"],
        "companies": ["Google", "Amazon", "Facebook"],
        "status": "active",
        "total_submissions": 0,
        "accepted_submissions": 0,
        "created_by": "system",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
]

async def setup_database():
    """Setup database with indexes and sample data"""
    
    # Connect to MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/compiler")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.get_database()
    
    print("=" * 60)
    print("Dynamic Problem System Setup")
    print("=" * 60)
    
    try:
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return
    
    # Create indexes
    print("\n📊 Creating database indexes...")
    
    try:
        # Problems collection indexes
        await db.problems.create_index([("problem_id", 1)], unique=True)
        await db.problems.create_index([("category", 1)])
        await db.problems.create_index([("difficulty", 1)])
        await db.problems.create_index([("status", 1)])
        await db.problems.create_index([("created_at", -1)])
        await db.problems.create_index([("tags", 1)])
        print("✅ Created indexes for problems collection")
        
        # Submissions collection indexes
        await db.submissions.create_index([("user_id", 1)])
        await db.submissions.create_index([("problem_id", 1)])
        await db.submissions.create_index([("status", 1)])
        await db.submissions.create_index([("submitted_at", -1)])
        await db.submissions.create_index([("user_id", 1), ("problem_id", 1)])
        print("✅ Created indexes for submissions collection")
        
        # Users collection indexes (if not already exist)
        await db.users.create_index([("email", 1)], unique=True)
        await db.users.create_index([("username", 1)], unique=True)
        print("✅ Created indexes for users collection")
        
    except Exception as e:
        print(f"⚠️  Some indexes might already exist: {e}")
    
    # Add sample problems
    print("\n📝 Adding sample problems...")
    
    for problem in SAMPLE_PROBLEMS:
        try:
            # Check if problem already exists
            existing = await db.problems.find_one({"problem_id": problem["problem_id"]})
            if existing:
                print(f"⏭️  Problem {problem['problem_id']} ({problem['title']}) already exists, skipping...")
            else:
                await db.problems.insert_one(problem)
                print(f"✅ Added Problem {problem['problem_id']}: {problem['title']}")
        except Exception as e:
            print(f"❌ Error adding problem {problem['problem_id']}: {e}")
    
    # Set admin user (update first user to be admin)
    print("\n👤 Setting up admin user...")
    try:
        # Find first user or ask for email
        first_user = await db.users.find_one()
        if first_user:
            result = await db.users.update_one(
                {"_id": first_user["_id"]},
                {"$set": {"is_admin": True}}
            )
            if result.modified_count > 0:
                print(f"✅ Made {first_user['email']} an admin")
            else:
                print(f"ℹ️  {first_user['email']} was already an admin")
        else:
            print("⚠️  No users found. Register a user first, then run this script again.")
    except Exception as e:
        print(f"❌ Error setting admin: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    
    problem_count = await db.problems.count_documents({"status": "active"})
    total_problems = await db.problems.count_documents({})
    user_count = await db.users.count_documents({})
    admin_count = await db.users.count_documents({"is_admin": True})
    
    print(f"📊 Active Problems: {problem_count}")
    print(f"📊 Total Problems: {total_problems}")
    print(f"👥 Total Users: {user_count}")
    print(f"👨‍💼 Admin Users: {admin_count}")
    
    print("\n✨ Setup complete!")
    print("\n📚 Next Steps:")
    print("1. Start your backend server")
    print("2. Login as admin user")
    print("3. Go to /api/docs to see admin endpoints")
    print("4. Use POST /api/admin/problems to create new problems")
    print("=" * 60)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(setup_database())










