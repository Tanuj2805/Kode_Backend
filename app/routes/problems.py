from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from ..models import SubmissionCreate, SubmissionResponse, LeaderboardEntry, ProblemListItem
from ..auth import get_current_user, get_current_user_optional
from ..database import get_database
import time
import asyncio

router = APIRouter()

# ============================================
# DYNAMIC PROBLEM SYSTEM - Using MongoDB
# ============================================

# Old hardcoded test cases kept as fallback
FALLBACK_TEST_CASES = {
    1: {  # Two Sum
        "test_cases": [
            {"input": "[2,7,11,15]\n9", "expected": "[0, 1]"},
            {"input": "[3,2,4]\n6", "expected": "[1, 2]"},
            {"input": "[3,3]\n6", "expected": "[0, 1]"},
            {"input": "[1,5,3,7,9]\n12", "expected": "[2, 4]"},
            {"input": "[-1,-2,-3,-4,-5]\n-8", "expected": "[2, 4]"},
        ],
        "time_limit": 5000,  # ms
        "memory_limit": 128000  # KB
    },
    2: {  # Reverse String
        "test_cases": [
            {"input": "hello", "expected": "olleh"},
            {"input": "Hannah", "expected": "hannaH"},
            {"input": "a", "expected": "a"},
            {"input": "python", "expected": "nohtyp"},
            {"input": "12345", "expected": "54321"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    3: {  # Palindrome Number
        "test_cases": [
            {"input": "121", "expected": "true"},
            {"input": "-121", "expected": "false"},
            {"input": "10", "expected": "false"},
            {"input": "12321", "expected": "true"},
            {"input": "0", "expected": "true"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    4: {  # Valid Parentheses
        "test_cases": [
            {"input": "()", "expected": "true"},
            {"input": "()[]{}", "expected": "true"},
            {"input": "(]", "expected": "false"},
            {"input": "([)]", "expected": "false"},
            {"input": "{[]}", "expected": "true"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    5: {  # Maximum Subarray
        "test_cases": [
            {"input": "[-2,1,-3,4,-1,2,1,-5,4]", "expected": "6"},
            {"input": "[1]", "expected": "1"},
            {"input": "[5,4,-1,7,8]", "expected": "23"},
            {"input": "[-1,-2,-3,-4]", "expected": "-1"},
            {"input": "[1,2,3,4,5]", "expected": "15"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    6: {  # Remove Duplicates
        "test_cases": [
            {"input": "[1,1,2]", "expected": "2"},
            {"input": "[0,0,1,1,1,2,2,3,3,4]", "expected": "5"},
            {"input": "[1,2,3]", "expected": "3"},
            {"input": "[1,1,1,1]", "expected": "1"},
            {"input": "[]", "expected": "0"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    7: {  # Search Insert Position
        "test_cases": [
            {"input": "[1,3,5,6]\n5", "expected": "2"},
            {"input": "[1,3,5,6]\n2", "expected": "1"},
            {"input": "[1,3,5,6]\n7", "expected": "4"},
            {"input": "[1,3,5,6]\n0", "expected": "0"},
            {"input": "[1]\n1", "expected": "0"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    8: {  # Climbing Stairs
        "test_cases": [
            {"input": "2", "expected": "2"},
            {"input": "3", "expected": "3"},
            {"input": "4", "expected": "5"},
            {"input": "5", "expected": "8"},
            {"input": "10", "expected": "89"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    9: {  # Merge Sorted Array
        "test_cases": [
            {"input": "[1,2,3,0,0,0]\n3\n[2,5,6]\n3", "expected": "[1,2,2,3,5,6]"},
            {"input": "[1]\n1\n[]\n0", "expected": "[1]"},
            {"input": "[0]\n0\n[1]\n1", "expected": "[1]"},
            {"input": "[4,5,6,0,0,0]\n3\n[1,2,3]\n3", "expected": "[1,2,3,4,5,6]"},
            {"input": "[1,2,4,5,6,0]\n5\n[3]\n1", "expected": "[1,2,3,4,5,6]"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    10: {  # Binary Tree Inorder
        "test_cases": [
            {"input": "[1,null,2,3]", "expected": "[1,3,2]"},
            {"input": "[]", "expected": "[]"},
            {"input": "[1]", "expected": "[1]"},
            {"input": "[1,2,3,4,5]", "expected": "[4,2,5,1,3]"},
            {"input": "[5,3,7,2,4,6,8]", "expected": "[2,3,4,5,6,7,8]"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    11: {  # Same Tree
        "test_cases": [
            {"input": "[1,2,3]\n[1,2,3]", "expected": "true"},
            {"input": "[1,2]\n[1,null,2]", "expected": "false"},
            {"input": "[1,2,1]\n[1,1,2]", "expected": "false"},
            {"input": "[]\n[]", "expected": "true"},
            {"input": "[1]\n[1]", "expected": "true"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    12: {  # Single Number
        "test_cases": [
            {"input": "[2,2,1]", "expected": "1"},
            {"input": "[4,1,2,1,2]", "expected": "4"},
            {"input": "[1]", "expected": "1"},
            {"input": "[7,3,5,3,7]", "expected": "5"},
            {"input": "[0,1,0,1,99]", "expected": "99"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    13: {  # Linked List Cycle
        "test_cases": [
            {"input": "[3,2,0,-4]\n1", "expected": "true"},
            {"input": "[1,2]\n0", "expected": "true"},
            {"input": "[1]\n-1", "expected": "false"},
            {"input": "[1,2,3,4]\n-1", "expected": "false"},
            {"input": "[1,2,3]\n2", "expected": "true"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    14: {  # Min Stack
        "test_cases": [
            {"input": "push:-2\npush:0\npush:-3\ngetMin\npop\ntop\ngetMin", "expected": "-3,0,-2"},
            {"input": "push:1\npush:2\ntop\npop\ngetMin", "expected": "2,1"},
            {"input": "push:5\ngetMin", "expected": "5"},
            {"input": "push:3\npush:1\npush:2\ngetMin\npop\ngetMin", "expected": "1,1"},
            {"input": "push:0\npush:1\npush:0\ngetMin\npop\ngetMin", "expected": "0,0"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    15: {  # Intersection of Arrays
        "test_cases": [
            {"input": "[1,2,2,1]\n[2,2]", "expected": "[2,2]"},
            {"input": "[4,9,5]\n[9,4,9,8,4]", "expected": "[4,9]"},
            {"input": "[1,2,3]\n[4,5,6]", "expected": "[]"},
            {"input": "[1]\n[1]", "expected": "[1]"},
            {"input": "[1,2,3,4,5]\n[5,4,3]", "expected": "[3,4,5]"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    16: {  # Majority Element
        "test_cases": [
            {"input": "[3,2,3]", "expected": "3"},
            {"input": "[2,2,1,1,1,2,2]", "expected": "2"},
            {"input": "[1]", "expected": "1"},
            {"input": "[6,5,5]", "expected": "5"},
            {"input": "[1,1,1,2,2,3,3,3,3]", "expected": "3"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    17: {  # Happy Number
        "test_cases": [
            {"input": "19", "expected": "true"},
            {"input": "2", "expected": "false"},
            {"input": "1", "expected": "true"},
            {"input": "7", "expected": "true"},
            {"input": "20", "expected": "false"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    18: {  # Remove Elements
        "test_cases": [
            {"input": "[3,2,2,3]\n3", "expected": "2"},
            {"input": "[0,1,2,2,3,0,4,2]\n2", "expected": "5"},
            {"input": "[1]\n1", "expected": "0"},
            {"input": "[4,5]\n4", "expected": "1"},
            {"input": "[]\n0", "expected": "0"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    19: {  # Count Primes
        "test_cases": [
            {"input": "10", "expected": "4"},
            {"input": "0", "expected": "0"},
            {"input": "1", "expected": "0"},
            {"input": "20", "expected": "8"},
            {"input": "100", "expected": "25"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    },
    20: {  # Isomorphic Strings
        "test_cases": [
            {"input": "egg\nadd", "expected": "true"},
            {"input": "foo\nbar", "expected": "false"},
            {"input": "paper\ntitle", "expected": "true"},
            {"input": "ab\naa", "expected": "false"},
            {"input": "abc\ncba", "expected": "true"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    }
}

# Generic test cases for problems 4-100
def get_generic_test_cases():
    return {
        "test_cases": [
            {"input": "test1", "expected": "output1"},
            {"input": "test2", "expected": "output2"},
            {"input": "test3", "expected": "output3"},
        ],
        "time_limit": 5000,
        "memory_limit": 128000
    }

@router.get("")
async def list_problems(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get all active problems with pagination and search (public endpoint)"""
    db = get_database()
    
    # Build query
    query = {"status": "active"}
    if category:
        query["category"] = category
    if difficulty:
        query["difficulty"] = difficulty
    if search:
        # Search in title and description using regex (case-insensitive)
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    # Get total count for pagination
    total_count = await db.problems.count_documents(query)
    
    # Get difficulty counts for filtered results
    easy_count = await db.problems.count_documents({**query, "difficulty": "Easy"})
    medium_count = await db.problems.count_documents({**query, "difficulty": "Medium"})
    hard_count = await db.problems.count_documents({**query, "difficulty": "Hard"})
    
    # Get problems (exclude test cases and sensitive data)
    cursor = db.problems.find(
        query,
        {
            "problem_id": 1,
            "title": 1,
            "difficulty": 1,
            "category": 1,
            "description": 1,
            "total_submissions": 1,
            "accepted_submissions": 1,
            "points": 1,
            "tags": 1,
            "companies": 1,
            "_id": 0
        }
    ).sort("problem_id", 1).skip(skip).limit(limit)
    
    problems = await cursor.to_list(length=limit)
    
    # Return problems with pagination metadata and difficulty counts
    return {
        "problems": problems,
        "total": total_count,
        "easy": easy_count,
        "medium": medium_count,
        "hard": hard_count,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + len(problems)) < total_count
    }

@router.get("/leaderboard")
async def get_leaderboard(
    skip: int = 0, 
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get leaderboard rankings with pagination - Requires login"""
    try:
        db = get_database()
        
        # First, get all user statistics to calculate proper ranks
        all_users_pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "username": {"$first": "$username"},
                    "total_submissions": {"$sum": 1},
                    "accepted_submissions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "Accepted"]}, 1, 0]}
                    },
                    "unique_problems": {"$addToSet": "$problem_id"},
                    "total_points": {"$sum": "$points"},
                    "last_submission": {"$max": "$submitted_at"}
                }
            },
            {
                "$project": {
                    "username": 1,
                    "total_submissions": 1,
                    "problems_solved": {"$size": "$unique_problems"},
                    "acceptance_rate": {
                        "$multiply": [
                            {"$divide": ["$accepted_submissions", "$total_submissions"]},
                            100
                        ]
                    },
                    "points": "$total_points",
                    "last_submission": 1
                }
            },
            {"$sort": {"points": -1, "problems_solved": -1, "total_submissions": 1}}
        ]
        
        all_users = await db.submissions.aggregate(all_users_pipeline).to_list(length=None)
        total_users = len(all_users)
        
        # Get paginated data
        paginated_users = all_users[skip:skip + limit]
        
        # Add rank and convert to list of dicts
        leaderboard = []
        for idx, entry in enumerate(paginated_users):
            actual_rank = skip + idx + 1
            leaderboard.append({
                "rank": actual_rank,
                "username": entry["username"],
                "problems_solved": entry["problems_solved"],
                "total_submissions": entry["total_submissions"],
                "acceptance_rate": round(entry["acceptance_rate"], 2),
                "points": entry["points"],
                "last_submission": entry.get("last_submission")
            })
        
        return {
            "leaderboard": leaderboard,
            "total": total_users,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + len(leaderboard)) < total_users
        }
    except Exception as e:
        print(f"[ERROR] Leaderboard error: {str(e)}")
        return {
            "leaderboard": [],
            "total": 0,
            "skip": 0,
            "limit": limit,
            "has_more": False
        }

@router.get("/leaderboard/my-rank")
async def get_my_rank(current_user: dict = Depends(get_current_user)):
    """Get current user's rank and stats"""
    try:
        db = get_database()
        
        # Get all user statistics to find rank
        all_users_pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "username": {"$first": "$username"},
                    "total_submissions": {"$sum": 1},
                    "accepted_submissions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "Accepted"]}, 1, 0]}
                    },
                    "unique_problems": {"$addToSet": "$problem_id"},
                    "total_points": {"$sum": "$points"}
                }
            },
            {
                "$project": {
                    "username": 1,
                    "total_submissions": 1,
                    "problems_solved": {"$size": "$unique_problems"},
                    "acceptance_rate": {
                        "$multiply": [
                            {"$divide": ["$accepted_submissions", "$total_submissions"]},
                            100
                        ]
                    },
                    "points": "$total_points"
                }
            },
            {"$sort": {"points": -1, "problems_solved": -1, "total_submissions": 1}}
        ]
        
        all_users = await db.submissions.aggregate(all_users_pipeline).to_list(length=None)
        
        # Find current user's rank
        my_rank = None
        my_stats = None
        for idx, entry in enumerate(all_users):
            if entry["username"] == current_user["username"]:
                my_rank = idx + 1
                my_stats = {
                    "rank": my_rank,
                    "username": entry["username"],
                    "problems_solved": entry["problems_solved"],
                    "total_submissions": entry["total_submissions"],
                    "acceptance_rate": round(entry["acceptance_rate"], 2),
                    "points": entry["points"]
                }
                break
        
        if not my_stats:
            # User has no submissions yet
            return {
                "rank": None,
                "username": current_user["username"],
                "problems_solved": 0,
                "total_submissions": 0,
                "acceptance_rate": 0,
                "points": 0,
                "total_users": len(all_users)
            }
        
        my_stats["total_users"] = len(all_users)
        return my_stats
        
    except Exception as e:
        print(f"[ERROR] My rank error: {str(e)}")
        return {
            "rank": None,
            "username": current_user["username"],
            "problems_solved": 0,
            "total_submissions": 0,
            "acceptance_rate": 0,
            "points": 0,
            "total_users": 0
        }

@router.get("/user-progress")
async def get_user_progress(current_user: dict = Depends(get_current_user)):
    """Get current user's problem-solving progress"""
    try:
        db = get_database()
        
        # Get unique problems solved by the user (Accepted submissions only)
        user_submissions = await db.submissions.find({
            "username": current_user["username"],
            "status": "Accepted"
        }).to_list(length=None)
        
        # Get unique problem IDs
        unique_problems = set(submission["problem_id"] for submission in user_submissions)
        solved_count = len(unique_problems)
        
        # Get total submissions
        total_submissions = await db.submissions.count_documents({
            "username": current_user["username"]
        })
        
        # Get accepted submissions
        accepted_submissions = len(user_submissions)
        
        # Calculate acceptance rate
        acceptance_rate = round((accepted_submissions / total_submissions * 100), 2) if total_submissions > 0 else 0
        
        return {
            "solvedCount": solved_count,
            "totalSubmissions": total_submissions,
            "acceptedSubmissions": accepted_submissions,
            "acceptanceRate": acceptance_rate,
            "problemIds": list(unique_problems)
        }
        
    except Exception as e:
        print(f"[ERROR] User progress error: {str(e)}")
        return {
            "solvedCount": 0,
            "totalSubmissions": 0,
            "acceptedSubmissions": 0,
            "acceptanceRate": 0,
            "problemIds": []
        }

@router.get("/{problem_id}", response_model=dict)
async def get_problem_details(
    problem_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed problem information (without hidden test cases)"""
    db = get_database()
    
    problem = await db.problems.find_one(
        {"problem_id": problem_id, "status": "active"},
        {
            "_id": 0,
            "created_by": 0,
            "created_at": 0,
            "updated_at": 0
        }
    )
    
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    # Filter out hidden test cases
    if "test_cases" in problem:
        problem["test_cases"] = [
            tc for tc in problem["test_cases"] 
            if not tc.get("hidden", False)
        ]
    
    return problem

@router.post("/run", response_model=dict)
async def run_problem_code(
    submission: SubmissionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Run code using Redis Queue + Worker (same as compiler run button)
    Only runs against visible test cases for quick feedback
    """
    from ..redis_queue_service import redis_queue_service
    from ..redis_service import redis_service
    import uuid
    import json
    import asyncio
    
    db = get_database()
    
    # Get problem from database
    problem = await db.problems.find_one({"problem_id": submission.problem_id, "status": "active"})
    
    if not problem:
        # Fallback to hardcoded test cases
        if submission.problem_id in FALLBACK_TEST_CASES:
            test_data = FALLBACK_TEST_CASES[submission.problem_id]
            test_cases = test_data["test_cases"]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem {submission.problem_id} not found"
            )
    else:
        # Get only VISIBLE test cases for run (not all hidden ones)
        all_test_cases = problem.get("test_cases", [])
        test_cases = [tc for tc in all_test_cases if not tc.get("hidden", False)]
        
        if not test_cases:
            # If no visible tests, use first test
            test_cases = all_test_cases[:1] if all_test_cases else []
    
    if not test_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No test cases available for this problem"
        )
    
    # Use FIRST test case for run (quick feedback)
    test_case = test_cases[0]
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create job data (same format as compiler run button)
    job_data = {
        "job_id": job_id,
        "language": submission.language,
        "code": submission.code,
        "input": test_case["input"],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Send to Redis Queue (same as compiler)
    await redis_queue_service.send_job(job_data)
    
    # Wait for result (same polling logic as compiler)
    result_key = f"result:{job_id}"
    max_wait_time = 30  # 30 seconds timeout
    poll_interval = 0.05  # Poll every 50ms
    elapsed_time = 0
    execution_result = None
    
    while elapsed_time < max_wait_time:
        result_data = redis_service.get(result_key)
        
        if result_data:
            execution_result = json.loads(result_data)
            redis_service.delete(result_key)  # Cleanup
            break
        
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
    
    # Handle timeout
    if execution_result is None:
        return {
            "status": "Error",
            "output": "",
            "error": "Execution timeout (30s)",
            "execution_time": 0,
            "test_case_used": {
                "input": test_case["input"],
                "expected": test_case.get("expected", "")
            }
        }
    
    # Return result (same format as compiler)
    return {
        "status": "Success" if execution_result.get("success") else "Error",
        "output": execution_result.get("output", ""),
        "error": execution_result.get("error"),
        "execution_time": execution_result.get("execution_time", 0),
        "test_case_used": {
            "input": test_case["input"],
            "expected": test_case.get("expected", "")
        }
    }

@router.post("/submit", response_model=dict)
async def submit_problem(
    submission: SubmissionCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a solution for a problem
    Uses Redis Queue + Code Wrapper (same as contest submit button)
    Runs ALL test cases in SINGLE execution
    """
    from ..redis_queue_service import redis_queue_service
    from ..redis_service import redis_service
    from ..code_wrapper import wrap_code_with_all_tests
    import uuid
    import json
    import asyncio
    
    db = get_database()
    
    # Get problem from database
    problem = await db.problems.find_one({"problem_id": submission.problem_id, "status": "active"})
    
    if not problem:
        # Fallback to hardcoded test cases if problem not in DB
        if submission.problem_id in FALLBACK_TEST_CASES:
            test_data = FALLBACK_TEST_CASES[submission.problem_id]
            test_cases = test_data["test_cases"]
            points = 100  # Default points for fallback
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem {submission.problem_id} not found"
            )
    else:
        # Get test cases from problem
        test_cases = problem.get("test_cases", [])
        points = problem.get("points", 100)
        
        if not test_cases:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No test cases available for this problem"
            )
    
    print(f"[INFO] Problem {submission.problem_id}: Testing code with {len(test_cases)} test cases")
    print(f"[DEBUG] Language: {submission.language}")
    
    # Wrap user's code with test runner that runs ALL test cases
    wrapped_code = wrap_code_with_all_tests(
        user_code=submission.code,
        test_cases=test_cases,
        problem_slug=f"problem_{submission.problem_id}",
        function_name="main",
        language=submission.language
    )
    
    print(f"[DEBUG] Wrapped code length: {len(wrapped_code)} chars")
    
    # Submit ONE job with wrapped code
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "language": submission.language,
        "code": wrapped_code,  # Code includes ALL test cases!
        "input": "",  # No input needed - tests are embedded
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await redis_queue_service.send_job(job_data)
    print(f"[INFO] Job {job_id} submitted to Redis Queue")
    
    # Wait for single result
    result_key = f"result:{job_id}"
    max_wait_time = 30  # 30 seconds timeout
    poll_interval = 0.05  # Poll every 50ms
    elapsed_time = 0
    execution_result = None
    
    while elapsed_time < max_wait_time:
        result_data = redis_service.get(result_key)
        
        if result_data:
            execution_result = json.loads(result_data)
            redis_service.delete(result_key)  # Cleanup
            break
        
        await asyncio.sleep(poll_interval)
        elapsed_time += poll_interval
    
    # Handle timeout
    if execution_result is None:
        print(f"[ERROR] Job {job_id} timed out after {max_wait_time}s")
        return {
            "status": "Error",
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "runtime_ms": 0,
            "language": submission.language,
            "points": 0,
            "test_results": [{
                "test_number": 1,
                "passed": False,
                "input": "",
                "expected": "",
                "actual": "",
                "error": "Execution timeout (30s)",
                "runtime_ms": 0
            }]
        }
    
    # Handle execution error
    if not execution_result.get("success"):
        print(f"[ERROR] Job {job_id} failed: {execution_result.get('error')}")
        return {
            "status": "Error",
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "runtime_ms": 0,
            "language": submission.language,
            "points": 0,
            "test_results": [{
                "test_number": 1,
                "passed": False,
                "input": "",
                "expected": "",
                "actual": "",
                "error": execution_result.get("error", "Runtime error"),
                "runtime_ms": 0
            }]
        }
    
    # Parse test results from output (JSON array)
    try:
        output_raw = execution_result.get("output", "[]")
        print(f"[DEBUG] Raw output from worker: {output_raw[:500]}")  # First 500 chars
        test_results = json.loads(output_raw)
        print(f"[DEBUG] Parsed {len(test_results)} test results")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Job {job_id}: Failed to parse test results: {e}")
        print(f"[ERROR] Raw output was: {execution_result.get('output', '')[:500]}")
        return {
            "status": "Error",
            "passed_tests": 0,
            "total_tests": len(test_cases),
            "runtime_ms": 0,
            "language": submission.language,
            "points": 0,
            "test_results": [{
                "test_number": 1,
                "passed": False,
                "input": "",
                "expected": "",
                "actual": "",
                "error": "Invalid test output format",
                "runtime_ms": 0
            }]
        }
    
    # Count passed tests
    passed_tests = sum(1 for t in test_results if t.get("passed"))
    total_tests = len(test_cases)
    status_result = "Accepted" if passed_tests == total_tests else "Wrong Answer"
    
    # Format test results for response (common for both compiled and interpreted)
    formatted_results = []
    for result in test_results:
        test_num = result.get("test_case", 0)
        test_case = test_cases[test_num - 1] if test_num <= len(test_cases) else {}
        
        # Include input for better debugging
        test_input = result.get("input", test_case.get("input", ""))
        
        # Get expected output (support both "expected" and "expected_output" field names)
        expected_output = result.get("expected", "")
        if not expected_output and test_case:
            expected_output = test_case.get("expected", test_case.get("expected_output", ""))
        
        formatted_results.append({
            "test_number": test_num,
            "passed": result.get("passed", False),
            "input": test_input if not test_case.get("hidden", False) else "Hidden",
            "expected": expected_output if not test_case.get("hidden", False) else "Hidden",
            "actual": result.get("actual", ""),
            "error": result.get("error"),
            "runtime_ms": 0  # Runtime not tracked per test in wrapped execution
        })
    
    # Determine final status
    status = status_result
    points_earned = points if status == "Accepted" else 0
    
    print(f"[INFO] Submission completed: {status} ({passed_tests}/{total_tests} tests passed)")
    
    # Update problem statistics if problem exists in DB (for all attempts)
    if problem:
        await db.problems.update_one(
            {"problem_id": submission.problem_id},
            {
                "$inc": {
                    "total_submissions": 1,
                    "accepted_submissions": 1 if status == "Accepted" else 0
                }
            }
        )
    
    # ONLY save submission to database if ALL tests passed
    if status == "Accepted":
        print(f"[INFO] All tests passed! Saving/updating submission to database.")
        
        # Check if user already solved this problem
        previous_acceptance = await db.submissions.find_one({
            "user_id": str(current_user["_id"]),
            "problem_id": submission.problem_id,
            "status": "Accepted"
        })
        
        # Prepare submission data
        submission_data = {
            "language": submission.language,
            "code": submission.code,
            "status": status,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "runtime_ms": int(execution_result.get("execution_time", 0) * 1000) if execution_result else 0,
            "memory_kb": 0,  # Memory tracking would need additional implementation
            "points": points_earned,
            "submitted_at": datetime.utcnow(),
            "test_results": formatted_results  # Use formatted results
        }
        
        if previous_acceptance:
            # UPDATE existing submission (user already solved this problem)
            await db.submissions.update_one(
                {
                    "user_id": str(current_user["_id"]),
                    "problem_id": submission.problem_id,
                    "status": "Accepted"
                },
                {"$set": submission_data}
            )
            print(f"[INFO] Updated existing submission (ID: {previous_acceptance['_id']}). No additional points awarded.")
        else:
            # INSERT new submission (first time solving this problem)
            submission_doc = {
                "user_id": str(current_user["_id"]),
                "username": current_user["username"],
                "problem_id": submission.problem_id,
                **submission_data
            }
            
            result = await db.submissions.insert_one(submission_doc)
            print(f"[INFO] New submission saved with ID: {result.inserted_id}")
            
            # Award points only for first time solving
            await db.users.update_one(
                {"_id": current_user["_id"]},
                {
                    "$inc": {"total_points": points_earned},
                    "$addToSet": {"solved_problems": submission.problem_id}
                }
            )
            print(f"[INFO] User earned {points_earned} points for solving problem {submission.problem_id}")
    else:
        print(f"[INFO] Tests failed ({status}). Submission NOT saved to database.")
    
    # Return response
    return {
        "status": status,
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "runtime_ms": int(execution_result.get("execution_time", 0) * 1000) if execution_result else 0,
        "language": submission.language,
        "points": points_earned,
        "test_results": formatted_results
    }

@router.get("/submissions/my", response_model=List[SubmissionResponse])
async def get_my_submissions(
    problem_id: int = None,
    current_user: dict = Depends(get_current_user)
):
    """Get current user's submissions"""
    db = get_database()
    
    query = {"user_id": current_user["_id"]}
    if problem_id:
        query["problem_id"] = problem_id
    
    submissions = await db.submissions.find(query).sort("submitted_at", -1).limit(50).to_list(length=50)
    
    for sub in submissions:
        sub["_id"] = str(sub["_id"])
        sub["user_id"] = str(sub["user_id"])
    
    return [SubmissionResponse(**sub) for sub in submissions]

@router.get("/problems/{problem_id}/status")
async def get_problem_status(
    problem_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get user's status for a specific problem"""
    db = get_database()
    
    # Find if user has solved this problem
    accepted = await db.submissions.find_one({
        "user_id": current_user["_id"],
        "problem_id": problem_id,
        "status": "Accepted"
    })
    
    # Get user's submissions for this problem
    submissions = await db.submissions.find({
        "user_id": current_user["_id"],
        "problem_id": problem_id
    }).sort("submitted_at", -1).limit(5).to_list(length=5)
    
    for sub in submissions:
        sub["_id"] = str(sub["_id"])
        sub["user_id"] = str(sub["user_id"])
    
    return {
        "solved": bool(accepted),
        "attempts": len(submissions),
        "recent_submissions": submissions
    }

@router.get("/stats/my")
async def get_my_stats(current_user: dict = Depends(get_current_user)):
    """Get current user's statistics"""
    db = get_database()
    
    pipeline = [
        {"$match": {"user_id": current_user["_id"]}},
        {
            "$group": {
                "_id": "$user_id",
                "total_submissions": {"$sum": 1},
                "accepted_submissions": {
                    "$sum": {"$cond": [{"$eq": ["$status", "Accepted"]}, 1, 0]}
                },
                "unique_problems": {"$addToSet": "$problem_id"},
                "total_points": {"$sum": "$points"}
            }
        },
        {
            "$project": {
                "total_submissions": 1,
                "problems_solved": {"$size": "$unique_problems"},
                "acceptance_rate": {
                    "$multiply": [
                        {"$divide": ["$accepted_submissions", "$total_submissions"]},
                        100
                    ]
                },
                "points": "$total_points"
            }
        }
    ]
    
    stats = await db.submissions.aggregate(pipeline).to_list(length=1)
    
    if stats:
        result = stats[0]
        return {
            "username": current_user["username"],
            "problems_solved": result["problems_solved"],
            "total_submissions": result["total_submissions"],
            "acceptance_rate": round(result["acceptance_rate"], 2),
            "points": result["points"]
        }
    
    return {
        "username": current_user["username"],
        "problems_solved": 0,
        "total_submissions": 0,
        "acceptance_rate": 0.0,
        "points": 0
    }

def update_user_stats(db, user_id):
    """Update user statistics after submission"""
    # This could be expanded to cache stats in user document
    pass

