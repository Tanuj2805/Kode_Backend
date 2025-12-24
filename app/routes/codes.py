from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.models import CodeCreate, CodeUpdate, CodeResponse
from app.auth import get_current_user
from app.database import get_database

router = APIRouter()

@router.get("/")
async def get_codes(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Number of records to return"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's saved codes with pagination and search.
    Returns: {codes: [...], total: int, page: int, totalPages: int}
    """
    try:
        db = get_database()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available. Please ensure MongoDB is installed and running."
        )
    
    # Build query
    query = {"user": str(current_user["_id"])}
    
    # Add search filter if provided
    if search and search.strip():
        search_pattern = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [
            {"title": search_pattern},
            {"description": search_pattern}
        ]
    
    # Get total count
    total = await db.codes.count_documents(query)
    
    # Get paginated codes
    codes = await db.codes.find(query).sort("updatedAt", -1).skip(skip).limit(limit).to_list(length=limit)
    
    # Convert ObjectId to string
    for code in codes:
        code["_id"] = str(code["_id"])
    
    # Calculate pagination info
    page = (skip // limit) + 1
    total_pages = (total + limit - 1) // limit  # Ceiling division
    
    return {
        "codes": codes,
        "total": total,
        "page": page,
        "totalPages": total_pages,
        "limit": limit
    }

@router.get("/{code_id}", response_model=CodeResponse)
async def get_code(code_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    
    try:
        code = await db.codes.find_one({"_id": ObjectId(code_id)})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if code["user"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to access this code"
        )
    
    code["_id"] = str(code["_id"])
    return code

@router.post("/", response_model=CodeResponse, status_code=status.HTTP_201_CREATED)
async def create_code(code: CodeCreate, current_user: dict = Depends(get_current_user)):
    db = get_database()
    
    code_dict = {
        "user": str(current_user["_id"]),
        "title": code.title,
        "language": code.language,
        "code": code.code,
        "description": code.description or "",
        "input": code.input or "",
        "folderPath": code.folderPath or "",
        "lastOutput": "",
        "lastRunAt": None,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    result = await db.codes.insert_one(code_dict)
    code_dict["_id"] = str(result.inserted_id)
    
    return code_dict

@router.put("/{code_id}", response_model=CodeResponse)
async def update_code(
    code_id: str,
    code_update: CodeUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    
    try:
        code = await db.codes.find_one({"_id": ObjectId(code_id)})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if code["user"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to update this code"
        )
    
    # Update fields
    update_dict = {"updatedAt": datetime.utcnow()}
    
    if code_update.title is not None:
        update_dict["title"] = code_update.title
    if code_update.language is not None:
        update_dict["language"] = code_update.language
    if code_update.code is not None:
        update_dict["code"] = code_update.code
    if code_update.description is not None:
        update_dict["description"] = code_update.description
    if code_update.input is not None:
        update_dict["input"] = code_update.input
    if code_update.lastOutput is not None:
        update_dict["lastOutput"] = code_update.lastOutput
        update_dict["lastRunAt"] = datetime.utcnow()
    if code_update.folderPath is not None:
        update_dict["folderPath"] = code_update.folderPath
    
    await db.codes.update_one({"_id": ObjectId(code_id)}, {"$set": update_dict})
    
    updated_code = await db.codes.find_one({"_id": ObjectId(code_id)})
    updated_code["_id"] = str(updated_code["_id"])
    
    return updated_code

@router.delete("/{code_id}")
async def delete_code(code_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    
    try:
        code = await db.codes.find_one({"_id": ObjectId(code_id)})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code not found")
    
    if code["user"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to delete this code"
        )
    
    await db.codes.delete_one({"_id": ObjectId(code_id)})
    
    return {"message": "Code removed"}

