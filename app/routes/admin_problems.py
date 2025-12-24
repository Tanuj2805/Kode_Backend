from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from ..models import (
    ProblemCreate, ProblemUpdate, ProblemResponse, ProblemListItem
)
from ..auth import get_admin_user, get_current_user
from ..database import get_database

router = APIRouter()

@router.post("/problems", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_problem(
    problem: ProblemCreate,
    current_user: dict = Depends(get_admin_user)
):
    """Create a new problem (Admin only)"""
    db = get_database()
    
    # Check if problem_id already exists
    existing = await db.problems.find_one({"problem_id": problem.problem_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Problem with ID {problem.problem_id} already exists"
        )
    
    # Create problem document
    problem_dict = problem.dict()
    problem_dict["created_by"] = current_user["email"]
    problem_dict["created_at"] = datetime.utcnow()
    problem_dict["updated_at"] = datetime.utcnow()
    problem_dict["total_submissions"] = 0
    problem_dict["accepted_submissions"] = 0
    
    # Insert into database
    result = await db.problems.insert_one(problem_dict)
    
    return {
        "message": "Problem created successfully",
        "problem_id": problem.problem_id,
        "id": str(result.inserted_id)
    }

@router.get("/problems/{problem_id}", response_model=dict)
async def get_problem_admin(
    problem_id: int,
    current_user: dict = Depends(get_admin_user)
):
    """Get full problem details including hidden test cases (Admin only)"""
    db = get_database()
    
    problem = await db.problems.find_one({"problem_id": problem_id})
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    # Convert ObjectId to string
    problem["_id"] = str(problem["_id"])
    
    return problem

@router.get("/problems", response_model=List[dict])
async def list_all_problems_admin(
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_admin_user)
):
    """List all problems with admin details"""
    db = get_database()
    
    # Build filter query
    query = {}
    if status_filter:
        query["status"] = status_filter
    if category:
        query["category"] = category
    if difficulty:
        query["difficulty"] = difficulty
    
    # Get problems with count
    cursor = db.problems.find(query).sort("problem_id", 1).skip(skip).limit(limit)
    problems = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string
    for problem in problems:
        problem["_id"] = str(problem["_id"])
        # Include test case count
        problem["test_case_count"] = len(problem.get("test_cases", []))
    
    return problems

@router.put("/problems/{problem_id}", response_model=dict)
async def update_problem(
    problem_id: int,
    problem_update: ProblemUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """Update an existing problem (Admin only)"""
    db = get_database()
    
    # Check if problem exists
    existing = await db.problems.find_one({"problem_id": problem_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    # Update only provided fields
    update_dict = {k: v for k, v in problem_update.dict().items() if v is not None}
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_dict["updated_at"] = datetime.utcnow()
    
    # Update in database
    await db.problems.update_one(
        {"problem_id": problem_id},
        {"$set": update_dict}
    )
    
    return {
        "message": "Problem updated successfully",
        "problem_id": problem_id,
        "updated_fields": list(update_dict.keys())
    }

@router.delete("/problems/{problem_id}", status_code=status.HTTP_200_OK)
async def delete_problem(
    problem_id: int,
    permanent: bool = False,
    current_user: dict = Depends(get_admin_user)
):
    """Delete a problem (soft delete by default, permanent if specified)"""
    db = get_database()
    
    if permanent:
        # Permanent delete
        result = await db.problems.delete_one({"problem_id": problem_id})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem {problem_id} not found"
            )
        return {
            "message": f"Problem {problem_id} permanently deleted",
            "permanent": True
        }
    else:
        # Soft delete (archive)
        result = await db.problems.update_one(
            {"problem_id": problem_id},
            {"$set": {"status": "archived", "updated_at": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Problem {problem_id} not found"
            )
        return {
            "message": f"Problem {problem_id} archived successfully",
            "permanent": False
        }

@router.get("/next-id", response_model=dict)
async def get_next_problem_id(current_user: dict = Depends(get_admin_user)):
    """Get the next available problem ID"""
    db = get_database()
    
    # Find the highest problem_id
    cursor = db.problems.find({}, {"problem_id": 1}).sort("problem_id", -1).limit(1)
    problems = await cursor.to_list(length=1)
    
    next_id = (problems[0]["problem_id"] + 1) if problems else 1
    
    return {"next_problem_id": next_id}

@router.get("/statistics", response_model=dict)
async def get_admin_statistics(current_user: dict = Depends(get_admin_user)):
    """Get overall problem statistics"""
    db = get_database()
    
    # Count problems by status
    active_count = await db.problems.count_documents({"status": "active"})
    draft_count = await db.problems.count_documents({"status": "draft"})
    archived_count = await db.problems.count_documents({"status": "archived"})
    
    # Count by difficulty
    easy_count = await db.problems.count_documents({"difficulty": "Easy", "status": "active"})
    medium_count = await db.problems.count_documents({"difficulty": "Medium", "status": "active"})
    hard_count = await db.problems.count_documents({"difficulty": "Hard", "status": "active"})
    
    # Total submissions
    total_submissions = await db.submissions.count_documents({})
    
    return {
        "total_problems": active_count + draft_count + archived_count,
        "active_problems": active_count,
        "draft_problems": draft_count,
        "archived_problems": archived_count,
        "by_difficulty": {
            "Easy": easy_count,
            "Medium": medium_count,
            "Hard": hard_count
        },
        "total_submissions": total_submissions
    }

@router.post("/problems/{problem_id}/test-cases", response_model=dict)
async def add_test_case(
    problem_id: int,
    test_case: dict,
    current_user: dict = Depends(get_admin_user)
):
    """Add a test case to a problem"""
    db = get_database()
    
    result = await db.problems.update_one(
        {"problem_id": problem_id},
        {
            "$push": {"test_cases": test_case},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    return {"message": "Test case added successfully"}

@router.delete("/problems/{problem_id}/test-cases/{index}", response_model=dict)
async def delete_test_case(
    problem_id: int,
    index: int,
    current_user: dict = Depends(get_admin_user)
):
    """Delete a test case from a problem by index"""
    db = get_database()
    
    # Get problem
    problem = await db.problems.find_one({"problem_id": problem_id})
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    # Check index
    test_cases = problem.get("test_cases", [])
    if index < 0 or index >= len(test_cases):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid test case index {index}"
        )
    
    # Remove test case
    test_cases.pop(index)
    
    await db.problems.update_one(
        {"problem_id": problem_id},
        {
            "$set": {
                "test_cases": test_cases,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": f"Test case {index} deleted successfully"}










