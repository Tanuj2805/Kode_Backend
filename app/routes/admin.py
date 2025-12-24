from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from ..models import InterviewExperienceResponse
from ..auth import get_admin_user
from ..database import get_database
from bson import ObjectId
from pydantic import BaseModel

router = APIRouter()

# ============== ADMIN MODELS ==============

class ProblemCreate(BaseModel):
    id: int
    title: str
    difficulty: str
    category: str
    description: str
    examples: Optional[list] = []
    constraints: Optional[list] = []
    companies: Optional[list] = []
    tags: Optional[list] = []

class ProblemUpdate(BaseModel):
    title: Optional[str] = None
    difficulty: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    examples: Optional[list] = None
    constraints: Optional[list] = None
    companies: Optional[list] = None
    tags: Optional[list] = None

# ============== ADMIN PROBLEM ROUTES ==============

@router.post("/problems")
async def create_problem(
    problem: ProblemCreate,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Create a new problem"""
    db = get_database()
    
    # Check if problem ID already exists
    existing = await db.problems.find_one({"id": problem.id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Problem with ID {problem.id} already exists"
        )
    
    problem_doc = problem.dict()
    problem_doc["created_by"] = admin_user["_id"]
    problem_doc["created_at"] = datetime.utcnow()
    problem_doc["updated_at"] = datetime.utcnow()
    
    await db.problems.insert_one(problem_doc)
    
    return {"message": "Problem created successfully", "problem_id": problem.id}

@router.put("/problems/{problem_id}")
async def update_problem(
    problem_id: int,
    problem_update: ProblemUpdate,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update an existing problem"""
    db = get_database()
    
    # Get existing problem
    existing = await db.problems.find_one({"id": problem_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    # Update only provided fields
    update_data = {k: v for k, v in problem_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    update_data["updated_by"] = admin_user["_id"]
    
    await db.problems.update_one(
        {"id": problem_id},
        {"$set": update_data}
    )
    
    return {"message": "Problem updated successfully", "problem_id": problem_id}

@router.delete("/problems/{problem_id}")
async def delete_problem(
    problem_id: int,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Delete a problem"""
    db = get_database()
    
    result = await db.problems.delete_one({"id": problem_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {problem_id} not found"
        )
    
    return {"message": "Problem deleted successfully", "problem_id": problem_id}

@router.get("/problems")
async def get_all_problems_admin(
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get all problems with metadata"""
    db = get_database()
    
    problems = await db.problems.find().sort("id", 1).to_list(length=1000)
    
    for problem in problems:
        problem["_id"] = str(problem["_id"])
        if "created_by" in problem:
            problem["created_by"] = str(problem["created_by"])
        if "updated_by" in problem:
            problem["updated_by"] = str(problem["updated_by"])
    
    return problems

# ============== ADMIN INTERVIEW EXPERIENCE ROUTES ==============

@router.delete("/interview-experiences/{experience_id}")
async def delete_experience(
    experience_id: str,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Delete an interview experience"""
    db = get_database()
    
    try:
        result = await db.interview_experiences.delete_one({"_id": ObjectId(experience_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experience not found"
            )
        
        return {"message": "Experience deleted successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid experience ID: {str(e)}"
        )

@router.put("/interview-experiences/{experience_id}")
async def update_experience(
    experience_id: str,
    update_data: dict,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Update an interview experience"""
    db = get_database()
    
    try:
        update_data["updated_at"] = datetime.utcnow()
        update_data["updated_by"] = admin_user["_id"]
        
        result = await db.interview_experiences.update_one(
            {"_id": ObjectId(experience_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experience not found"
            )
        
        return {"message": "Experience updated successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating experience: {str(e)}"
        )

@router.get("/interview-experiences")
async def get_all_experiences_admin(
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get all interview experiences"""
    db = get_database()
    
    experiences = await db.interview_experiences.find().sort("created_at", -1).to_list(length=1000)
    
    for exp in experiences:
        exp["_id"] = str(exp["_id"])
        exp["user_id"] = str(exp["user_id"])
    
    return experiences

# ============== ADMIN USER MANAGEMENT ==============

@router.get("/users")
async def get_all_users(
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get all users"""
    db = get_database()
    
    users = await db.users.find().to_list(length=10000)
    
    for user in users:
        user["_id"] = str(user["_id"])
        # Don't send password hashes
        user.pop("password", None)
    
    return users

@router.put("/users/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    make_admin: bool,
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Make a user admin or remove admin rights"""
    db = get_database()
    
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_admin": make_admin}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        action = "granted" if make_admin else "revoked"
        return {"message": f"Admin rights {action} successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating user: {str(e)}"
        )

@router.get("/stats")
async def get_admin_stats(
    admin_user: dict = Depends(get_admin_user)
):
    """Admin: Get platform statistics"""
    db = get_database()
    
    stats = {
        "total_users": await db.users.countDocuments(),
        "total_submissions": await db.submissions.countDocuments(),
        "total_problems": await db.problems.countDocuments(),
        "total_solutions": await db.solutions.countDocuments(),
        "total_experiences": await db.interview_experiences.countDocuments(),
        "accepted_submissions": await db.submissions.countDocuments({"status": "Accepted"}),
        "admin_users": await db.users.countDocuments({"is_admin": True})
    }
    
    return stats










