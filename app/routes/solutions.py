from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from ..models import (
    SolutionCreate, 
    SolutionResponse, 
    SolutionVote,
    InterviewExperienceCreate,
    InterviewExperienceResponse,
    InterviewExperienceHelpful
)
from ..auth import get_current_user, get_current_user_optional
from ..database import get_database
from bson import ObjectId

router = APIRouter()

# ============== SOLUTIONS ROUTES ==============

@router.post("/solutions", response_model=SolutionResponse)
async def create_solution(
    solution: SolutionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new solution for a problem - Only logged-in users"""
    db = get_database()
    
    solution_doc = {
        "problem_id": solution.problem_id,
        "user_id": current_user["_id"],
        "username": current_user["username"],
        "language": solution.language,
        "title": solution.title,
        "explanation": solution.explanation,
        "code": solution.code,
        "time_complexity": solution.time_complexity or "",
        "space_complexity": solution.space_complexity or "",
        "upvotes": 0,
        "downvotes": 0,
        "created_at": datetime.utcnow(),
        "is_verified": False  # Can be set to True by admins later
    }
    
    result = await db.solutions.insert_one(solution_doc)
    solution_doc["_id"] = str(result.inserted_id)
    solution_doc["user_id"] = str(solution_doc["user_id"])
    
    return SolutionResponse(**solution_doc)


@router.get("/solutions/problem/{problem_id}", response_model=List[SolutionResponse])
async def get_solutions_by_problem(
    problem_id: int,
    language: Optional[str] = None,
    limit: int = 50
):
    """Get all solutions for a specific problem - Public access"""
    db = get_database()
    
    query = {"problem_id": problem_id}
    if language:
        query["language"] = language
    
    # Sort by upvotes and verification status
    solutions_cursor = db.solutions.find(query).sort([("is_verified", -1), ("upvotes", -1), ("created_at", -1)]).limit(limit)
    solutions = await solutions_cursor.to_list(length=limit)
    
    for sol in solutions:
        sol["_id"] = str(sol["_id"])
        sol["user_id"] = str(sol["user_id"])
    
    return [SolutionResponse(**sol) for sol in solutions]


@router.get("/solutions/{solution_id}", response_model=SolutionResponse)
async def get_solution_by_id(solution_id: str):
    """Get a specific solution by ID - Public access"""
    db = get_database()
    
    try:
        solution = await db.solutions.find_one({"_id": ObjectId(solution_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid solution ID")
    
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    
    solution["_id"] = str(solution["_id"])
    solution["user_id"] = str(solution["user_id"])
    
    return SolutionResponse(**solution)


@router.post("/solutions/{solution_id}/vote")
async def vote_solution(
    solution_id: str,
    vote: SolutionVote,
    current_user: dict = Depends(get_current_user)
):
    """Vote on a solution (upvote/downvote) - Only logged-in users"""
    db = get_database()
    
    try:
        solution_obj_id = ObjectId(solution_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid solution ID")
    
    # Check if solution exists
    solution = await db.solutions.find_one({"_id": solution_obj_id})
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")
    
    # Check if user already voted
    existing_vote = await db.solution_votes.find_one({
        "user_id": current_user["_id"],
        "solution_id": solution_obj_id
    })
    
    if existing_vote:
        # Update vote
        old_vote = existing_vote["vote_type"]
        
        if old_vote == vote.vote_type:
            # Remove vote
            await db.solution_votes.delete_one({"_id": existing_vote["_id"]})
            
            if vote.vote_type == "upvote":
                await db.solutions.update_one(
                    {"_id": solution_obj_id},
                    {"$inc": {"upvotes": -1}}
                )
            else:
                await db.solutions.update_one(
                    {"_id": solution_obj_id},
                    {"$inc": {"downvotes": -1}}
                )
            
            return {"message": "Vote removed", "action": "removed"}
        else:
            # Change vote
            await db.solution_votes.update_one(
                {"_id": existing_vote["_id"]},
                {"$set": {"vote_type": vote.vote_type}}
            )
            
            if vote.vote_type == "upvote":
                await db.solutions.update_one(
                    {"_id": solution_obj_id},
                    {"$inc": {"upvotes": 1, "downvotes": -1}}
                )
            else:
                await db.solutions.update_one(
                    {"_id": solution_obj_id},
                    {"$inc": {"upvotes": -1, "downvotes": 1}}
                )
            
            return {"message": f"Vote changed to {vote.vote_type}", "action": "changed"}
    else:
        # Add new vote
        await db.solution_votes.insert_one({
            "user_id": current_user["_id"],
            "solution_id": solution_obj_id,
            "vote_type": vote.vote_type,
            "created_at": datetime.utcnow()
        })
        
        if vote.vote_type == "upvote":
            await db.solutions.update_one(
                {"_id": solution_obj_id},
                {"$inc": {"upvotes": 1}}
            )
        else:
            await db.solutions.update_one(
                {"_id": solution_obj_id},
                {"$inc": {"downvotes": 1}}
            )
        
        return {"message": f"Voted {vote.vote_type}", "action": "added"}


@router.get("/solutions/user/my", response_model=List[SolutionResponse])
async def get_my_solutions(
    current_user: dict = Depends(get_current_user),
    limit: int = 50
):
    """Get current user's solutions"""
    db = get_database()
    
    solutions_cursor = db.solutions.find({"user_id": current_user["_id"]}).sort("created_at", -1).limit(limit)
    solutions = await solutions_cursor.to_list(length=limit)
    
    for sol in solutions:
        sol["_id"] = str(sol["_id"])
        sol["user_id"] = str(sol["user_id"])
    
    return [SolutionResponse(**sol) for sol in solutions]


# ============== INTERVIEW EXPERIENCES ROUTES ==============

@router.post("/interview-experiences", response_model=InterviewExperienceResponse)
async def create_interview_experience(
    experience: InterviewExperienceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new interview experience - Only logged-in users"""
    db = get_database()
    
    # Use "Anonymous" if user wants to remain anonymous
    display_username = "Anonymous" if experience.is_anonymous else current_user["username"]
    
    experience_doc = {
        "user_id": current_user["_id"],
        "username": display_username,
        "company": experience.company,
        "job_role": experience.job_role,
        "location": experience.location,
        "years_of_experience": experience.years_of_experience,
        "salary": experience.salary,  # Include salary field (optional)
        "linkedin_profile": experience.linkedin_profile if not experience.is_anonymous else None,
        "interview_date": experience.interview_date,
        "difficulty": experience.difficulty,
        "rounds": experience.rounds,
        "questions_asked": experience.questions_asked,
        "overall_experience": experience.overall_experience,
        "tips": experience.tips or "",
        "offer_received": experience.offer_received,
        "is_anonymous": experience.is_anonymous,
        "helpful_count": 0,
        "created_at": datetime.utcnow()
    }
    
    result = await db.interview_experiences.insert_one(experience_doc)
    experience_doc["_id"] = str(result.inserted_id)
    experience_doc["user_id"] = str(experience_doc["user_id"])
    
    return InterviewExperienceResponse(**experience_doc)


@router.get("/interview-experiences", response_model=List[InterviewExperienceResponse])
async def get_interview_experiences(
    company: Optional[str] = None,
    difficulty: Optional[str] = None,
    experience_level: Optional[str] = None,
    job_role: Optional[str] = None,
    sort_by: Optional[str] = "recent",  # "recent" or "popular"
    skip: int = 0,
    limit: int = 60,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get interview experiences list - Limited to 6 for non-logged users, full access for logged users"""
    db = get_database()
    
    # Limit results to 6 for non-logged users (teaser mode)
    is_logged_in = current_user is not None
    if not is_logged_in:
        limit = min(limit, 6)
        skip = 0  # Non-logged users can't paginate
    
    query = {}
    if company:
        query["company"] = {"$regex": company, "$options": "i"}
    if difficulty:
        query["difficulty"] = difficulty
    if job_role:
        query["job_role"] = {"$regex": job_role, "$options": "i"}
    if experience_level:
        # Parse experience level ranges like "0-1", "1-3", "3-5", "5-10", "10+"
        if experience_level == "0-1":
            query["years_of_experience"] = {"$gte": 0, "$lte": 1}
        elif experience_level == "1-3":
            query["years_of_experience"] = {"$gte": 1, "$lte": 3}
        elif experience_level == "3-5":
            query["years_of_experience"] = {"$gte": 3, "$lte": 5}
        elif experience_level == "5-10":
            query["years_of_experience"] = {"$gte": 5, "$lte": 10}
        elif experience_level == "10+":
            query["years_of_experience"] = {"$gte": 10}
    else:
        # When no experience level filter is selected, only require years_of_experience to exist
        query["years_of_experience"] = {"$exists": True}
    
    # Determine sort order based on sort_by parameter
    if sort_by == "popular":
        sort_order = [("helpful_count", -1), ("created_at", -1)]
    else:  # default to "recent"
        sort_order = [("created_at", -1)]
    
    experiences_cursor = db.interview_experiences.find(query).sort(sort_order).skip(skip).limit(limit)
    experiences = await experiences_cursor.to_list(length=limit)
    
    for exp in experiences:
        exp["_id"] = str(exp["_id"])
        exp["user_id"] = str(exp["user_id"])
        # Ensure salary field exists for backwards compatibility with older records
        if "salary" not in exp:
            exp["salary"] = None
    
    return [InterviewExperienceResponse(**exp) for exp in experiences]


@router.get("/interview-experiences/company/{company}", response_model=List[InterviewExperienceResponse])
async def get_experiences_by_company(
    company: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)  # Only logged-in users can view
):
    """Get interview experiences for a specific company - Only logged-in users"""
    db = get_database()
    
    # Only get records with years_of_experience (skip old schema)
    query = {
        "company": {"$regex": company, "$options": "i"},
        "years_of_experience": {"$exists": True}
    }
    experiences_cursor = db.interview_experiences.find(query).sort([("helpful_count", -1), ("created_at", -1)]).limit(limit)
    experiences = await experiences_cursor.to_list(length=limit)
    
    for exp in experiences:
        exp["_id"] = str(exp["_id"])
        exp["user_id"] = str(exp["user_id"])
        # Ensure salary field exists for backwards compatibility with older records
        if "salary" not in exp:
            exp["salary"] = None
    
    return [InterviewExperienceResponse(**exp) for exp in experiences]


@router.get("/interview-experiences/{experience_id}", response_model=InterviewExperienceResponse)
async def get_interview_experience_by_id(
    experience_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific interview experience - Requires login"""
    db = get_database()
    
    try:
        experience = await db.interview_experiences.find_one({"_id": ObjectId(experience_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid experience ID")
    
    if not experience:
        raise HTTPException(status_code=404, detail="Interview experience not found")
    
    experience["_id"] = str(experience["_id"])
    experience["user_id"] = str(experience["user_id"])
    
    # Ensure salary field exists for backwards compatibility with older records
    if "salary" not in experience:
        experience["salary"] = None
    
    return InterviewExperienceResponse(**experience)


@router.post("/interview-experiences/{experience_id}/helpful")
async def mark_experience_helpful(
    experience_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark an interview experience as helpful - Only logged-in users"""
    db = get_database()
    
    try:
        experience_obj_id = ObjectId(experience_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid experience ID")
    
    # Check if experience exists
    experience = await db.interview_experiences.find_one({"_id": experience_obj_id})
    if not experience:
        raise HTTPException(status_code=404, detail="Interview experience not found")
    
    # Check if user already marked it helpful
    existing_helpful = await db.experience_helpful.find_one({
        "user_id": current_user["_id"],
        "experience_id": experience_obj_id
    })
    
    if existing_helpful:
        # Remove helpful mark
        await db.experience_helpful.delete_one({"_id": existing_helpful["_id"]})
        await db.interview_experiences.update_one(
            {"_id": experience_obj_id},
            {"$inc": {"helpful_count": -1}}
        )
        return {"message": "Helpful mark removed", "action": "removed"}
    else:
        # Add helpful mark
        await db.experience_helpful.insert_one({
            "user_id": current_user["_id"],
            "experience_id": experience_obj_id,
            "created_at": datetime.utcnow()
        })
        await db.interview_experiences.update_one(
            {"_id": experience_obj_id},
            {"$inc": {"helpful_count": 1}}
        )
        return {"message": "Marked as helpful", "action": "added"}


@router.get("/interview-experiences/user/my", response_model=List[InterviewExperienceResponse])
async def get_my_interview_experiences(
    current_user: dict = Depends(get_current_user),
    limit: int = 50
):
    """Get current user's interview experiences"""
    db = get_database()
    
    # Only get records with years_of_experience
    query = {
        "user_id": current_user["_id"],
        "years_of_experience": {"$exists": True}
    }
    experiences_cursor = db.interview_experiences.find(query).sort("created_at", -1).limit(limit)
    experiences = await experiences_cursor.to_list(length=limit)
    
    for exp in experiences:
        exp["_id"] = str(exp["_id"])
        exp["user_id"] = str(exp["user_id"])
        # Ensure salary field exists for backwards compatibility with older records
        if "salary" not in exp:
            exp["salary"] = None
    
    return [InterviewExperienceResponse(**exp) for exp in experiences]


# ============== COMPANIES LIST ==============

@router.get("/companies")
async def get_companies_list(current_user: Optional[dict] = Depends(get_current_user_optional)):
    """Get list of all companies with interview experiences (public endpoint)"""
    db = get_database()
    
    try:
        # Get distinct companies (only from new schema records)
        companies = await db.interview_experiences.distinct("company", {"years_of_experience": {"$exists": True}})
        
        # Get count for each company
        company_data = []
        for company in companies:
            count = await db.interview_experiences.count_documents({
                "company": company,
                "years_of_experience": {"$exists": True}
            })
            company_data.append({
                "name": company,
                "count": count
            })
        
        # Sort by count (descending)
        company_data.sort(key=lambda x: x["count"], reverse=True)
        
        return {"companies": company_data}
    except Exception as e:
        print(f"Error loading companies: {e}")
        return {"companies": []}


@router.get("/job-roles")
async def get_job_roles_list(
    company: Optional[str] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get list of job roles with interview experiences - optionally filtered by company (public endpoint)"""
    db = get_database()
    
    try:
        # Build query filter
        query = {"years_of_experience": {"$exists": True}}
        if company:
            query["company"] = {"$regex": company, "$options": "i"}
        
        # Get distinct job roles (filtered by company if provided)
        job_roles = await db.interview_experiences.distinct("job_role", query)
        
        # Get count for each job role (within the company filter if provided)
        job_role_data = []
        for role in job_roles:
            role_query = {
                "job_role": role,
                "years_of_experience": {"$exists": True}
            }
            if company:
                role_query["company"] = {"$regex": company, "$options": "i"}
                
            count = await db.interview_experiences.count_documents(role_query)
            job_role_data.append({
                "name": role,
                "count": count
            })
        
        # Sort by count (descending)
        job_role_data.sort(key=lambda x: x["count"], reverse=True)
        
        return {"job_roles": job_role_data}
    except Exception as e:
        print(f"Error loading job roles: {e}")
        return {"job_roles": []}

