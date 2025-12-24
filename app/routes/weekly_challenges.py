from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from ..models import (
    WeeklyChallengeCreate, WeeklyChallengeResponse, 
    WeeklyChallengeSubmission, WeeklyChallengeProgress,
    WeeklyStreak, WeeklyChallengeSubmissionRequest
)
from ..auth import get_current_user, get_current_user_optional, get_admin_user
from ..database import get_database, get_database_optional, is_database_connected
import time
import asyncio
from dotenv import load_dotenv, find_dotenv
import os
from pathlib import Path
import logging
import traceback
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see all messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Load environment variables for Redis configuration
# Explicitly find .env file from backend directory (3 levels up from this file)
backend_dir = Path(__file__).parent.parent.parent
dotenv_path = backend_dir / '.env'
load_dotenv(dotenv_path=dotenv_path, override=True)

# Debug: Verify .env was loaded
print(f"[INIT] Loading .env from: {dotenv_path}")
print(f"[INIT] .env exists: {dotenv_path.exists()}")

router = APIRouter()

# Helper function to get current week info
def get_current_week_info():
    now = datetime.utcnow()
    return {
        "year": now.isocalendar()[0],
        "week": now.isocalendar()[1]
    }

# Helper function to format week identifier
def format_week_identifier(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"

# ============================================
# PUBLIC ENDPOINTS
# ============================================

@router.get("/current")
async def get_current_challenge(
    contest_type: Optional[str] = Query(None, regex="^(weekly|normal)$"),
    current_user: dict = Depends(get_current_user)
):
    """Get all currently active challenges (supports multiple concurrent contests)
    
    Args:
        contest_type: Filter by contest type (weekly/normal). If not provided, returns all active contests.
    """
    try:
        # Check if database is connected
        if not is_database_connected():
            raise HTTPException(
                status_code=503,
                detail="Database not available. Weekly challenges require MongoDB to be running."
            )
        
        db = get_database()
        now = datetime.utcnow()
        
        # Build filter query
        query = {
            "status": "active",
            "start_date": {"$lte": now},
            "end_date": {"$gte": now}
        }
        
        # Add contest_type filter if specified
        if contest_type:
            query["contest_type"] = contest_type
        
        # Find ALL active challenges matching the filter
        challenges_cursor = db.weekly_challenges.find(query).sort("week_number", 1)
        
        challenges = await challenges_cursor.to_list(length=None)
        
        if not challenges:
            # Check for upcoming challenge
            upcoming = await db.weekly_challenges.find_one({
                "status": "upcoming",
                "start_date": {"$gt": now}
            }, sort=[("start_date", 1)])
            
            if upcoming:
                return {
                    "current_challenges": [],
                    "upcoming_challenge": {
                        "week_number": upcoming["week_number"],
                        "year": upcoming["year"],
                        "title": upcoming["title"],
                        "start_date": upcoming["start_date"].isoformat()
                    }
                }
            
            return {"current_challenges": [], "upcoming_challenge": None}
        
        # Process each challenge with user's progress
        result_challenges = []
        for challenge in challenges:
            # Get user's progress for this challenge
            progress = await db.weekly_challenge_progress.find_one({
                "user_id": str(current_user["_id"]),
                "challenge_id": str(challenge["_id"])
            })
            
            # Hide test cases for security
            for question in challenge["questions"]:
                if "test_cases" in question:
                    # Only show sample test cases
                    question["sample_test_cases"] = [tc for tc in question["test_cases"] if not tc.get("hidden", False)][:2]
                    del question["test_cases"]
            
            challenge["_id"] = str(challenge["_id"])
            challenge["start_date"] = challenge["start_date"].isoformat()
            challenge["end_date"] = challenge["end_date"].isoformat()
            challenge["created_at"] = challenge["created_at"].isoformat()
            challenge["my_progress"] = {
                "questions_solved": progress["questions_solved"] if progress else [],
                "total_points": progress["total_points"] if progress else 0
            }
            
            result_challenges.append(challenge)
        
        return {
            "current_challenges": result_challenges,
            "upcoming_challenge": None
        }
        
    except Exception as e:
        print(f"[ERROR] Get current challenge error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch current challenge")

@router.get("/weekly")
async def get_weekly_contests(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get all currently active WEEKLY contests (public endpoint)"""
    try:
        # Check if database is connected
        if not is_database_connected():
            raise HTTPException(
                status_code=503,
                detail="Database not available. Weekly challenges require MongoDB to be running."
            )
        
        db = get_database()
        now = datetime.utcnow()
        
        # Only check status - removed date filters
        # This allows users to see rankings for 2-3 days after contest ends
        # Admin controls visibility by changing status to "archived" when ready to hide
        challenges_cursor = db.weekly_challenges.find({
            "contest_type": "weekly",
            "status": "active"
        }).sort("week_number", -1)
        
        challenges = await challenges_cursor.to_list(length=None)
        
        # Process each challenge with user's progress (if logged in)
        result_challenges = []
        for challenge in challenges:
            # Only fetch progress if user is logged in
            progress = None
            if current_user:
                progress = await db.weekly_challenge_progress.find_one({
                    "user_id": str(current_user["_id"]),
                    "challenge_id": str(challenge["_id"])
                })
            
            # Hide test cases for security
            for question in challenge["questions"]:
                if "test_cases" in question:
                    question["sample_test_cases"] = [tc for tc in question["test_cases"] if not tc.get("hidden", False)][:2]
                    del question["test_cases"]
            
            challenge["_id"] = str(challenge["_id"])
            challenge["start_date"] = challenge["start_date"].isoformat()
            challenge["end_date"] = challenge["end_date"].isoformat()
            challenge["created_at"] = challenge["created_at"].isoformat()
            challenge["my_progress"] = {
                "questions_solved": progress["questions_solved"] if progress else [],
                "total_points": progress["total_points"] if progress else 0
            }
            
            result_challenges.append(challenge)
        
        return {"contests": result_challenges}
        
    except Exception as e:
        print(f"[ERROR] Get weekly contests error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch weekly contests")

@router.get("/normal")
async def get_normal_contests(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get all currently active NORMAL contests (public endpoint)"""
    try:
        db = get_database()
        now = datetime.utcnow()
        
        # Only check status - removed date filters
        # This allows users to see rankings for 2-3 days after contest ends
        # Admin controls visibility by changing status to "archived" when ready to hide
        challenges_cursor = db.weekly_challenges.find({
            "contest_type": "normal",
            "status": "active"
        }).sort("created_at", -1)
        
        challenges = await challenges_cursor.to_list(length=None)
        
        # Process each challenge with user's progress (if logged in)
        result_challenges = []
        for challenge in challenges:
            # Only fetch progress if user is logged in
            progress = None
            if current_user:
                progress = await db.weekly_challenge_progress.find_one({
                    "user_id": str(current_user["_id"]),
                    "challenge_id": str(challenge["_id"])
                })
            
            # Hide test cases for security
            for question in challenge["questions"]:
                if "test_cases" in question:
                    question["sample_test_cases"] = [tc for tc in question["test_cases"] if not tc.get("hidden", False)][:2]
                    del question["test_cases"]
            
            challenge["_id"] = str(challenge["_id"])
            challenge["start_date"] = challenge["start_date"].isoformat()
            challenge["end_date"] = challenge["end_date"].isoformat()
            challenge["created_at"] = challenge["created_at"].isoformat()
            challenge["my_progress"] = {
                "questions_solved": progress["questions_solved"] if progress else [],
                "total_points": progress["total_points"] if progress else 0
            }
            
            result_challenges.append(challenge)
        
        return {"contests": result_challenges}
        
    except Exception as e:
        print(f"[ERROR] Get normal contests error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch normal contests")

@router.get("/calendar")
async def get_challenges_calendar(
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get calendar view of all challenges (public endpoint)"""
    try:
        db = get_database()
        now = datetime.utcnow()
        
        # Get current active challenge
        current = await db.weekly_challenges.find_one({
            "status": "active",
            "start_date": {"$lte": now},
            "end_date": {"$gte": now}
        })
        
        # Get upcoming challenges (next 8 weeks)
        upcoming_cursor = db.weekly_challenges.find({
            "$or": [
                {"status": "upcoming"},
                {"start_date": {"$gt": now}}
            ]
        }).sort("start_date", 1).limit(8)
        upcoming = await upcoming_cursor.to_list(length=8)
        
        # Get recent past challenges (last 4 weeks)
        past_cursor = db.weekly_challenges.find({
            "status": "completed",
            "end_date": {"$lt": now}
        }).sort("end_date", -1).limit(4)
        past = await past_cursor.to_list(length=4)
        
        # Format challenges
        def format_challenge(c):
            if c:
                c["_id"] = str(c["_id"])
                c["start_date"] = c["start_date"].isoformat()
                c["end_date"] = c["end_date"].isoformat()
                c["created_at"] = c["created_at"].isoformat()
                # Remove test cases and just keep question count
                c["question_count"] = len(c.get("questions", []))
                del c["questions"]
            return c
        
        if current:
            format_challenge(current)
        
        for c in upcoming:
            format_challenge(c)
        
        for c in past:
            format_challenge(c)
        
        return {
            "current": current,
            "upcoming": upcoming,
            "past": past
        }
        
    except Exception as e:
        print(f"[ERROR] Get calendar error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch calendar")

@router.get("/past")
async def get_past_challenges(
    skip: int = 0, 
    limit: int = 10,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get past completed challenges"""
    try:
        db = get_database()
        
        cursor = db.weekly_challenges.find({
            "status": "completed"
        }).sort("end_date", -1).skip(skip).limit(limit)
        
        challenges = await cursor.to_list(length=limit)
        total = await db.weekly_challenges.count_documents({"status": "completed"})
        
        # Format challenges
        for challenge in challenges:
            challenge["_id"] = str(challenge["_id"])
            challenge["start_date"] = challenge["start_date"].isoformat()
            challenge["end_date"] = challenge["end_date"].isoformat()
            challenge["created_at"] = challenge["created_at"].isoformat()
            # Remove test cases from past challenges
            for question in challenge.get("questions", []):
                if "test_cases" in question:
                    del question["test_cases"]
        
        return {
            "challenges": challenges,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        print(f"[ERROR] Get past challenges error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch past challenges")

@router.get("/leaderboard")
async def get_weekly_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get overall weekly contest leaderboard based on streaks (public endpoint)"""
    try:
        db = get_database()
        
        # Get leaderboard from weekly_streaks collection
        # Sort by current_streak (descending), then by longest_streak, then by total_challenges_completed
        cursor = db.weekly_streaks.find().sort([
            ("current_streak", -1),
            ("longest_streak", -1),
            ("total_challenges_completed", -1)
        ]).limit(limit)
        
        leaderboard = await cursor.to_list(length=limit)
        
        # Format the results
        for idx, entry in enumerate(leaderboard):
            entry["rank"] = idx + 1
            entry["_id"] = str(entry["_id"])
            if entry.get("last_participation"):
                entry["last_participation"] = entry["last_participation"].isoformat()
        
        # Get current user's position (only if logged in)
        my_rank = None
        if current_user:
            user_streak = await db.weekly_streaks.find_one({"user_id": str(current_user["_id"])})
            
            if user_streak:
                # Count how many users have better stats
                better_count = await db.weekly_streaks.count_documents({
                    "$or": [
                        {"current_streak": {"$gt": user_streak.get("current_streak", 0)}},
                        {
                            "current_streak": user_streak.get("current_streak", 0),
                            "longest_streak": {"$gt": user_streak.get("longest_streak", 0)}
                        },
                        {
                            "current_streak": user_streak.get("current_streak", 0),
                            "longest_streak": user_streak.get("longest_streak", 0),
                            "total_challenges_completed": {"$gt": user_streak.get("total_challenges_completed", 0)}
                        }
                    ]
                })
                my_rank = better_count + 1
        
        return {
            "leaderboard": leaderboard,
            "my_rank": my_rank,
            "total": await db.weekly_streaks.count_documents({})
        }
        
    except Exception as e:
        print(f"[ERROR] Get weekly leaderboard error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch leaderboard: {str(e)}")

# OLD ENDPOINT REMOVED - Using paginated endpoint at line ~960 instead
# This duplicate was causing pagination issues (NaN participants)

@router.get("/{challenge_id}")
async def get_challenge_by_id(
    challenge_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific challenge by ID"""
    try:
        db = get_database()
        
        challenge = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Hide test cases
        for question in challenge["questions"]:
            if "test_cases" in question:
                question["sample_test_cases"] = [tc for tc in question["test_cases"] if not tc.get("hidden", False)][:2]
                del question["test_cases"]
        
        challenge["_id"] = str(challenge["_id"])
        challenge["start_date"] = challenge["start_date"].isoformat()
        challenge["end_date"] = challenge["end_date"].isoformat()
        challenge["created_at"] = challenge["created_at"].isoformat()
        
        # Get user's progress
        progress = await db.weekly_challenge_progress.find_one({
            "user_id": str(current_user["_id"]),
            "challenge_id": challenge_id
        })
        
        return {
            "challenge": challenge,
            "my_progress": {
                "questions_solved": progress["questions_solved"] if progress else [],
                "total_points": progress["total_points"] if progress else 0
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Get challenge by ID error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch challenge")

@router.post("/{challenge_id}/question/{question_number}/submit")
async def submit_challenge_question(
    challenge_id: str,
    question_number: int,
    submission: WeeklyChallengeSubmissionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Submit solution for a specific question in the challenge"""
    try:
        db = get_database()
        
        # Get challenge
        challenge = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Check if challenge is active
        now = datetime.utcnow()
        if challenge["status"] != "active" or now < challenge["start_date"] or now > challenge["end_date"]:
            raise HTTPException(status_code=400, detail="Challenge is not currently active")
        
        # Find the question
        question = next((q for q in challenge["questions"] if q["question_number"] == question_number), None)
        
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Execute code against ALL test cases in SINGLE execution (OPTIMIZED)
        import uuid
        import json
        import asyncio
        from ..redis_queue_service import redis_queue_service
        from ..redis_service import redis_service
        from ..code_wrapper import wrap_code_with_all_tests
        
        # Wrap user's code with test runner that runs ALL test cases
        problem_slug = question.get("problem_slug")  # e.g., "two_sum"
        function_name = question.get("function_name")  # e.g., "twoSum"
        test_cases = question["test_cases"]  # ALL test cases from MongoDB
        
        # Wrap code with all test cases embedded
        wrapped_code = wrap_code_with_all_tests(
            user_code=submission.code,
            test_cases=test_cases,
            problem_slug=problem_slug or "generic",
            function_name=function_name or "main",
            language=submission.language
        )
        
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
        
        # Wait for result using Pub/Sub (NOT polling!)
        from ..routes.execute_redis import pending_jobs
        
        # Create future to wait for result
        result_future = asyncio.Future()
        pending_jobs[job_id] = result_future
        

        try:
            # Wait for result with 60 second timeout (test cases can take time)
            execution_result = await asyncio.wait_for(result_future, timeout=60.0)
        except asyncio.TimeoutError:
            # Clean up
            if job_id in pending_jobs:
                del pending_jobs[job_id]
            
            # Handle timeout
            return {
                "status": "Error",
                "passed_tests": 0,
                "total_tests": len(test_cases),
                "points_earned": 0,
                "test_results": [{
                    "test_case": 1,
                    "status": "Failed",
                    "passed": False,
                    "error": "Execution timeout (60s)"
                }],
                "message": "Code execution timed out. Please optimize your solution."
            }
        finally:
            # Cleanup
            if job_id in pending_jobs:
                del pending_jobs[job_id]
        
        # Handle execution error
        if not execution_result.get("success"):
            return {
                "status": "Error",
                "passed_tests": 0,
                "total_tests": len(test_cases),
                "points_earned": 0,
                "test_results": [{
                    "test_case": 1,
                    "status": "Failed",
                    "passed": False,
                    "error": execution_result.get("error", "Runtime error")
                }],
                "message": "Code execution failed. Check the error message."
            }
        
        # Parse test results from output (JSON array)
        try:
            test_results = json.loads(execution_result.get("output", "[]"))
        except json.JSONDecodeError:
            return {
                "status": "Error",
                "passed_tests": 0,
                "total_tests": len(test_cases),
                "points_earned": 0,
                "test_results": [{
                    "test_case": 1,
                    "status": "Failed",
                    "passed": False,
                    "error": "Invalid test output format"
                }],
                "message": "Failed to parse test results."
            }
        
        # Count passed tests
        passed_count = sum(1 for t in test_results if t.get("passed"))
        total_tests = len(test_cases)
        
        # Format test results for response
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
                "test_case": test_num,
                "status": "Passed" if result.get("passed") else "Failed",
                "passed": result.get("passed", False),
                "input": test_input if not test_case.get("hidden", False) else "Hidden",
                "expected": expected_output if not test_case.get("hidden", False) else "Hidden",
                "actual": result.get("actual", ""),
                "error": result.get("error")
            })
        
        # FAIL-FAST: If first result is failure, return immediately
        if formatted_results and not formatted_results[0]["passed"]:
            failed_test = formatted_results[0]
            
            # Create helpful error message
            error_msg = f"Test case {failed_test['test_case']} failed."
            if failed_test.get("error"):
                error_msg += f" Error: {failed_test['error']}"
            else:
                error_msg += " Check your output format and logic."
            
            return {
                "status": "Wrong Answer",
                "passed_tests": 0,
                "total_tests": total_tests,
                "points_earned": 0,
                "test_results": [failed_test],  # Only the failed one with input shown
                "early_exit": True,
                "message": error_msg
            }
        
        # All tests passed or need to show multiple results
        
        # Sort test results by test case number
        formatted_results.sort(key=lambda x: x["test_case"])
        
        # Determine submission status
        total_tests = len(question["test_cases"])
        status = "Accepted" if passed_count == total_tests else "Wrong Answer"
        points_earned = question.get("points", 10) if status == "Accepted" else 0
        
        # Save submission
        submission_doc = {
            "user_id": str(current_user["_id"]),
            "username": current_user["username"],
            "challenge_id": challenge_id,
            "week_number": challenge["week_number"],
            "year": challenge["year"],
            "question_number": question_number,
            "code": submission.code,
            "language": submission.language,
            "status": status,
            "passed_tests": passed_count,
            "total_tests": total_tests,
            "points_earned": points_earned,
            "submitted_at": datetime.utcnow()
        }
        
        await db.weekly_challenge_submissions.insert_one(submission_doc)
        
        # Update user progress
        if status == "Accepted":
            progress = await db.weekly_challenge_progress.find_one({
                "user_id": str(current_user["_id"]),
                "challenge_id": challenge_id
            })
            
            if progress:
                if question_number not in progress["questions_solved"]:
                    await db.weekly_challenge_progress.update_one(
                        {"_id": progress["_id"]},
                        {
                            "$addToSet": {"questions_solved": question_number},
                            "$inc": {"total_points": points_earned}
                        }
                    )
            else:
                await db.weekly_challenge_progress.insert_one({
                    "user_id": str(current_user["_id"]),
                    "username": current_user["username"],
                    "challenge_id": challenge_id,
                    "week_number": challenge["week_number"],
                    "year": challenge["year"],
                    "questions_solved": [question_number],
                    "total_points": points_earned,
                    "completed_at": None
                })
            
            # Update streak (only for weekly contests)
            contest_type = challenge.get("contest_type", "weekly")
            if contest_type == "weekly":
                week_identifier = format_week_identifier(challenge["year"], challenge["week_number"])
                await update_user_streak(str(current_user["_id"]), current_user["username"], week_identifier, challenge_id)
        
        # Return success with all test cases passed message
        return {
            "status": status,
            "passed_tests": passed_count,
            "total_tests": total_tests,
            "points_earned": points_earned,
            "test_results": formatted_results,
            "message": f"🎉 All {total_tests} test cases passed! Solution accepted!"
        }
    
    except HTTPException:
         # Let FastAPI return the correct status & message
        raise

    except Exception as e:
        logger.info(f"[ERROR] Submit challenge question error: {str(e)}")
        logger.info(traceback.format_exc())                    
        print(f"[ERROR] Submit challenge question error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to submit solution: {str(e)}")

async def get_contests_between(last_challenge_id: str, current_challenge_id: str):
    """
    Get all WEEKLY contests between last and current participation (exclusive).
    Returns list of challenge IDs that existed between these two contests.
    
    Simple logic: Get all weekly contests, find contests between last and current.
    Only weekly contests count for streak calculation.
    """
    db = get_database()
    
    # Get the last and current contest details
    last_contest = await db.weekly_challenges.find_one({"_id": ObjectId(last_challenge_id)})
    current_contest = await db.weekly_challenges.find_one({"_id": ObjectId(current_challenge_id)})
    
    if not last_contest or not current_contest:
        return []
    
    # Get all WEEKLY contests between these two (by end_date)
    # Only weekly contests count for streak calculation
    contests_cursor = db.weekly_challenges.find({
        "contest_type": "weekly",  # Only weekly contests
        "status": {"$in": ["active", "completed"]},
        "end_date": {
            "$gt": last_contest["end_date"],
            "$lt": current_contest["end_date"]
        }
    }).sort("end_date", 1)
    
    contests = await contests_cursor.to_list(length=None)
    
    return [str(c["_id"]) for c in contests]

async def get_user_participated_contests(user_id: str):
    """
    Get list of all contest IDs where user participated.
    Returns list of challenge IDs.
    """
    db = get_database()
    
    progress_cursor = db.weekly_challenge_progress.find({
        "user_id": user_id
    })
    
    progress_list = await progress_cursor.to_list(length=None)
    
    return [p["challenge_id"] for p in progress_list]

async def update_user_streak(user_id: str, username: str, week_identifier: str, challenge_id: str):
    """
    Update user's weekly challenge streak.
    
    SIMPLE CONTEST-BASED LOGIC:
    - Streak = Consecutive CONTESTS solved (not weeks)
    - If user solves Contest 1, 2, 3 → Streak continues
    - If user skips Contest 2 → Streak breaks
    - Week numbers don't matter, only contest participation
    """
    db = get_database()
    
    streak = await db.weekly_streaks.find_one({"user_id": user_id})
    
    if not streak:
        # Create new streak - first contest participation
        await db.weekly_streaks.insert_one({
            "user_id": user_id,
            "username": username,
            "current_streak": 1,
            "longest_streak": 1,
            "weeks_participated": [week_identifier],
            "contests_participated": [challenge_id],  # Track by contest ID
            "total_challenges_completed": 0,
            "last_participation": datetime.utcnow(),
            "last_challenge_id": challenge_id
        })
        print(f"[STREAK] User {username} - First contest! Streak: 1")
    else:
        if challenge_id not in streak.get("contests_participated", []):
            # Get all contests user has participated in
            user_contests = await get_user_participated_contests(user_id)
            
            # Get last contest user participated in
            last_challenge_id = streak.get("last_challenge_id")
            
            is_consecutive = False
            
            if last_challenge_id:
                # Find all contests between last and current participation
                contests_between = await get_contests_between(last_challenge_id, challenge_id)
                
                if len(contests_between) == 0:
                    # No contests in between - consecutive!
                    is_consecutive = True
                    print(f"[STREAK] No contests between last and current - Consecutive!")
                else:
                    # Check if user participated in ALL contests in between
                    all_participated = all(
                        contest_id in user_contests 
                        for contest_id in contests_between
                    )
                    is_consecutive = all_participated
                    
                    if not all_participated:
                        missed = [c for c in contests_between if c not in user_contests]
                        print(f"[STREAK] User missed {len(missed)} contests - Streak breaks!")
                    else:
                        print(f"[STREAK] User participated in all {len(contests_between)} intermediate contests - Consecutive!")
            else:
                # No previous challenge found, start new streak
                is_consecutive = False
                print(f"[STREAK] No previous challenge found - Starting new streak")
            
            new_streak = (streak["current_streak"] + 1) if is_consecutive else 1
            new_longest = max(streak["longest_streak"], new_streak)
            
            # Update streak with contest tracking
            update_data = {
                "current_streak": new_streak,
                "longest_streak": new_longest,
                "last_participation": datetime.utcnow(),
                "last_challenge_id": challenge_id
            }
            
            await db.weekly_streaks.update_one(
                {"_id": streak["_id"]},
                {
                    "$set": update_data,
                    "$addToSet": {
                        "weeks_participated": week_identifier,
                        "contests_participated": challenge_id
                    }
                }
            )
            
            # Log streak update
            print(f"[STREAK] User {username} - Contest {challenge_id}")
            print(f"[STREAK] Is consecutive: {is_consecutive}")
            print(f"[STREAK] New streak: {new_streak}, Longest: {new_longest}")

@router.get("/my/progress")
async def get_my_progress(current_user: dict = Depends(get_current_user)):
    """Get user's overall weekly challenge progress"""
    try:
        # Check if database is connected
        if not is_database_connected():
            raise HTTPException(
                status_code=503,
                detail="Database not available. Weekly challenges require MongoDB to be running."
            )
        
        db = get_database()
        
        # Get streak
        streak = await db.weekly_streaks.find_one({"user_id": str(current_user["_id"])})
        
        # Get all progress
        progress_cursor = db.weekly_challenge_progress.find({
            "user_id": str(current_user["_id"])
        }).sort("year", -1).sort("week_number", -1)
        
        progress_list = await progress_cursor.to_list(length=None)
        
        return {
            "streak": {
                "current_streak": streak["current_streak"] if streak else 0,
                "longest_streak": streak["longest_streak"] if streak else 0,
                "weeks_participated": len(streak["weeks_participated"]) if streak else 0,
                "last_participation": streak["last_participation"].isoformat() if streak and streak.get("last_participation") else None
            },
            "progress": [
                {
                    "challenge_id": p["challenge_id"],
                    "week_number": p["week_number"],
                    "year": p["year"],
                    "questions_solved": p["questions_solved"],
                    "total_points": p["total_points"]
                }
                for p in progress_list
            ]
        }
        
    except Exception as e:
        print(f"[ERROR] Get my progress error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch progress")

@router.get("/{challenge_id}/leaderboard")
async def get_challenge_leaderboard(
    challenge_id: str,
    skip: int = 0,
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get leaderboard for a specific challenge"""
    try:
        db = get_database()
        
        # Get challenge info to get question count
        challenge = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        challenge_questions_count = len(challenge.get("questions", []))
        
        # Get total count
        total = await db.weekly_challenge_progress.count_documents({
            "challenge_id": challenge_id
        })
        
        cursor = db.weekly_challenge_progress.find({
            "challenge_id": challenge_id
        }).sort([
            ("total_points", -1),
            ("questions_solved", -1)
        ]).skip(skip).limit(limit)
        
        leaderboard = await cursor.to_list(length=limit)
        
        # Add ranks (based on actual position, not page position)
        for idx, entry in enumerate(leaderboard):
            entry["rank"] = skip + idx + 1
            entry["_id"] = str(entry["_id"])
        
        return {
            "leaderboard": leaderboard,
            "total": total,
            "skip": skip,
            "limit": limit,
            "challenge_questions_count": challenge_questions_count
        }
        
    except Exception as e:
        print(f"[ERROR] Get challenge leaderboard error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")

# ============================================
# ADMIN ENDPOINTS
# ============================================

@router.post("/admin/create", status_code=status.HTTP_201_CREATED)
async def create_weekly_challenge(
    challenge: WeeklyChallengeCreate,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Create a new weekly challenge"""
    try:
        db = get_database()
        
        # Check if challenge already exists for this week
        existing = await db.weekly_challenges.find_one({
            "week_number": challenge.week_number,
            "year": challenge.year
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Challenge already exists for this week")
        
        # Create challenge document
        challenge_doc = challenge.model_dump() if hasattr(challenge, 'model_dump') else challenge.dict()
        challenge_doc["created_at"] = datetime.utcnow()
        challenge_doc["total_participants"] = 0
        
        result = await db.weekly_challenges.insert_one(challenge_doc)
        
        return {
            "message": "Weekly challenge created successfully",
            "challenge_id": str(result.inserted_id)
        }
        
    except Exception as e:
        print(f"[ERROR] Create weekly challenge error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create challenge: {str(e)}")

@router.post("/admin/migrate-contest-types")
async def migrate_contest_types(admin_user: dict = Depends(get_admin_user)):
    """Admin: Migrate existing contests to add contest_type field (defaults to 'weekly')"""
    try:
        db = get_database()
        
        # Update all contests without contest_type field
        result = await db.weekly_challenges.update_many(
            {"contest_type": {"$exists": False}},
            {"$set": {"contest_type": "weekly"}}
        )
        
        return {
            "message": "Migration completed successfully",
            "modified_count": result.modified_count,
            "matched_count": result.matched_count
        }
        
    except Exception as e:
        print(f"[ERROR] Migration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@router.get("/admin/all")
async def get_all_challenges_admin(
    skip: int = 0,
    limit: int = 20,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get all weekly challenges with full details"""
    try:
        db = get_database()
        
        cursor = db.weekly_challenges.find().sort("created_at", -1).skip(skip).limit(limit)
        challenges = await cursor.to_list(length=limit)
        total = await db.weekly_challenges.count_documents({})
        
        for challenge in challenges:
            challenge["_id"] = str(challenge["_id"])
            challenge["start_date"] = challenge["start_date"].isoformat()
            challenge["end_date"] = challenge["end_date"].isoformat()
            challenge["created_at"] = challenge["created_at"].isoformat()
            # Keep test cases for admin
        
        return {
            "challenges": challenges,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        print(f"[ERROR] Get all challenges admin error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch challenges")

@router.get("/admin/{challenge_id}")
async def get_challenge_admin(
    challenge_id: str,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get a specific challenge with all details including test cases"""
    try:
        db = get_database()
        
        challenge = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        challenge["_id"] = str(challenge["_id"])
        challenge["start_date"] = challenge["start_date"].isoformat()
        challenge["end_date"] = challenge["end_date"].isoformat()
        challenge["created_at"] = challenge["created_at"].isoformat()
        
        # Get statistics
        progress_count = await db.weekly_challenge_progress.count_documents({
            "challenge_id": challenge_id
        })
        submissions_count = await db.weekly_challenge_submissions.count_documents({
            "challenge_id": challenge_id
        })
        
        challenge["stats"] = {
            "participants": progress_count,
            "total_submissions": submissions_count
        }
        
        return challenge
        
    except Exception as e:
        print(f"[ERROR] Get challenge admin error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch challenge")

@router.put("/admin/{challenge_id}")
async def update_challenge(
    challenge_id: str,
    challenge_update: WeeklyChallengeCreate,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update an existing weekly challenge"""
    try:
        db = get_database()
        
        # Check if challenge exists
        existing = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Update challenge
        update_doc = challenge_update.model_dump() if hasattr(challenge_update, 'model_dump') else challenge_update.dict()
        result = await db.weekly_challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": update_doc}
        )
        
        return {
            "message": "Challenge updated successfully",
            "challenge_id": challenge_id
        }
        
    except Exception as e:
        print(f"[ERROR] Update challenge error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update challenge: {str(e)}")

@router.patch("/admin/{challenge_id}/contest-type")
async def update_contest_type(
    challenge_id: str,
    contest_type: str = Query(..., regex="^(weekly|normal)$"),
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update only the contest_type field of a specific challenge"""
    try:
        db = get_database()
        
        # Check if challenge exists
        existing = await db.weekly_challenges.find_one({"_id": ObjectId(challenge_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Update only the contest_type field
        result = await db.weekly_challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": {"contest_type": contest_type}}
        )
        
        if result.modified_count == 0:
            return {
                "message": "Contest type was already set to this value",
                "challenge_id": challenge_id,
                "contest_type": contest_type
            }
        
        return {
            "message": f"Contest type updated to '{contest_type}' successfully",
            "challenge_id": challenge_id,
            "contest_type": contest_type,
            "previous_type": existing.get("contest_type", "not set")
        }
        
    except Exception as e:
        print(f"[ERROR] Update contest type error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update contest type: {str(e)}")

@router.delete("/admin/{challenge_id}")
async def delete_challenge(
    challenge_id: str,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Delete a weekly challenge and its associated data"""
    try:
        db = get_database()
        
        # Delete challenge
        result = await db.weekly_challenges.delete_one({"_id": ObjectId(challenge_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Delete associated progress and submissions
        await db.weekly_challenge_progress.delete_many({"challenge_id": challenge_id})
        await db.weekly_challenge_submissions.delete_many({"challenge_id": challenge_id})
        
        return {
            "message": "Challenge and associated data deleted successfully",
            "challenge_id": challenge_id
        }
        
    except Exception as e:
        print(f"[ERROR] Delete challenge error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete challenge")

@router.patch("/admin/{challenge_id}")
async def patch_challenge_fields(
    challenge_id: str,
    update_data: dict,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update any fields of a challenge (flexible partial update)"""
    try:
        db = get_database()
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided to update")
        
        # Build update document
        update_doc = {}
        
        # Handle date fields
        if "start_date" in update_data:
            try:
                update_doc["start_date"] = datetime.fromisoformat(update_data["start_date"].replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO 8601: YYYY-MM-DDTHH:MM:SS")
        
        if "end_date" in update_data:
            try:
                update_doc["end_date"] = datetime.fromisoformat(update_data["end_date"].replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO 8601: YYYY-MM-DDTHH:MM:SS")
        
        # Handle other fields
        allowed_fields = [
            "week_number", "year", "title", "description", "status", 
            "questions", "total_participants"
        ]
        
        for field in allowed_fields:
            if field in update_data:
                update_doc[field] = update_data[field]
        
        # Validate status if provided
        if "status" in update_doc:
            if update_doc["status"] not in ["upcoming", "active", "completed"]:
                raise HTTPException(status_code=400, detail="Invalid status. Must be: upcoming, active, or completed")
        
        # Validate dates if both provided
        if "start_date" in update_doc and "end_date" in update_doc:
            if update_doc["start_date"] >= update_doc["end_date"]:
                raise HTTPException(status_code=400, detail="Start date must be before end date")
        
        if not update_doc:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        # Update the challenge
        result = await db.weekly_challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": update_doc}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        updated_fields = ", ".join(update_doc.keys())
        return {
            "message": f"Challenge updated successfully",
            "updated_fields": list(update_doc.keys()),
            "challenge_id": challenge_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Patch challenge fields error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update challenge: {str(e)}")

@router.put("/admin/{challenge_id}/status")
async def update_challenge_status(
    challenge_id: str,
    new_status: str,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update challenge status (upcoming, active, completed)"""
    try:
        db = get_database()
        
        if new_status not in ["upcoming", "active", "completed"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be: upcoming, active, or completed")
        
        result = await db.weekly_challenges.update_one(
            {"_id": ObjectId(challenge_id)},
            {"$set": {"status": new_status}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        return {"message": f"Challenge status updated to {new_status}"}
        
    except Exception as e:
        print(f"[ERROR] Update challenge status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update status")

