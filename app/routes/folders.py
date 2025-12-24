from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from datetime import datetime
from bson import ObjectId
from app.models import FolderCreate, FolderResponse
from app.auth import get_current_user
from app.database import get_database

router = APIRouter()

@router.get("/", response_model=List[FolderResponse])
async def get_folders(current_user: dict = Depends(get_current_user)):
    """Get all folders for the current user"""
    try:
        db = get_database()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )
    
    folders = await db.folders.find({"user": str(current_user["_id"])}).sort("path", 1).to_list(length=None)
    
    # Convert ObjectId to string
    for folder in folders:
        folder["_id"] = str(folder["_id"])
    
    return folders

@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(folder: FolderCreate, current_user: dict = Depends(get_current_user)):
    """Create a new folder"""
    db = get_database()
    
    # Clean the path
    path = folder.path.strip().strip('/')
    
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid folder path"
        )
    
    # Check if folder already exists
    existing = await db.folders.find_one({
        "user": str(current_user["_id"]),
        "path": path
    })
    
    if existing:
        # Return existing folder instead of error
        existing["_id"] = str(existing["_id"])
        return existing
    
    # Create all parent folders if they don't exist
    path_parts = path.split('/')
    for i in range(len(path_parts)):
        parent_path = '/'.join(path_parts[:i+1])
        existing_parent = await db.folders.find_one({
            "user": str(current_user["_id"]),
            "path": parent_path
        })
        
        if not existing_parent:
            parent_folder_dict = {
                "user": str(current_user["_id"]),
                "path": parent_path,
                "createdAt": datetime.utcnow()
            }
            await db.folders.insert_one(parent_folder_dict)
    
    # Get the final folder
    final_folder = await db.folders.find_one({
        "user": str(current_user["_id"]),
        "path": path
    })
    
    final_folder["_id"] = str(final_folder["_id"])
    return final_folder

@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a folder (recursively - deletes all contents)"""
    db = get_database()
    
    try:
        folder = await db.folders.find_one({"_id": ObjectId(folder_id)})
    except:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    
    if folder["user"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to delete this folder"
        )
    
    path = folder["path"]
    
    # Count files that will be deleted
    files_count = await db.codes.count_documents({
        "user": str(current_user["_id"]),
        "folderPath": {"$regex": f"^{path}"}
    })
    
    # Count subfolders that will be deleted
    subfolders_count = await db.folders.count_documents({
        "user": str(current_user["_id"]),
        "path": {"$regex": f"^{path}/"}
    })
    
    # Delete all files in this folder and subfolders
    await db.codes.delete_many({
        "user": str(current_user["_id"]),
        "folderPath": {"$regex": f"^{path}"}
    })
    
    # Delete all subfolders
    await db.folders.delete_many({
        "user": str(current_user["_id"]),
        "path": {"$regex": f"^{path}"}
    })
    
    # Delete the folder itself
    await db.folders.delete_one({"_id": ObjectId(folder_id)})
    
    return {
        "message": "Folder deleted",
        "files_deleted": files_count,
        "folders_deleted": subfolders_count + 1
    }

@router.delete("/path/{path:path}")
async def delete_folder_by_path(path: str, current_user: dict = Depends(get_current_user)):
    """Delete a folder by path (recursively - deletes all contents)"""
    db = get_database()
    
    folder = await db.folders.find_one({
        "user": str(current_user["_id"]),
        "path": path
    })
    
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    
    # Count files that will be deleted
    files_count = await db.codes.count_documents({
        "user": str(current_user["_id"]),
        "folderPath": {"$regex": f"^{path}"}
    })
    
    # Count subfolders that will be deleted
    subfolders_count = await db.folders.count_documents({
        "user": str(current_user["_id"]),
        "path": {"$regex": f"^{path}/"}
    })
    
    # Delete all files in this folder and subfolders
    await db.codes.delete_many({
        "user": str(current_user["_id"]),
        "folderPath": {"$regex": f"^{path}"}
    })
    
    # Delete all subfolders
    await db.folders.delete_many({
        "user": str(current_user["_id"]),
        "path": {"$regex": f"^{path}"}
    })
    
    # Delete the folder itself
    await db.folders.delete_one({"_id": folder["_id"]})
    
    return {
        "message": "Folder deleted",
        "files_deleted": files_count,
        "folders_deleted": subfolders_count + 1
    }

