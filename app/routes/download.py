from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import get_database
import zipfile
import io

router = APIRouter()

class DownloadFolderRequest(BaseModel):
    folderPath: str

@router.post("/download/folder")
async def download_folder(
    request: DownloadFolderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Download all files in a folder as ZIP
    
    Request Body:
    {
        "folderPath": "my-project"
    }
    
    Response: ZIP file
    """
    
    db = get_database()
    folder_path = request.folderPath
    
    # Fetch all files in this folder AND subfolders (recursive)
    files = await db.codes.find({
        "user": str(current_user["_id"]),
        "$or": [
            {"folderPath": folder_path},                    # Exact match: files directly in folder
            {"folderPath": {"$regex": f"^{folder_path}/"}}  # Prefix match: files in subfolders
        ]
    }).to_list(length=1000)
    
    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"No files found in folder: {folder_path}"
        )
    
    print(f"[DOWNLOAD] Creating ZIP for folder: {folder_path} ({len(files)} files)")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file in files:
                # Get filename and ensure it has extension (same logic as UI)
                filename = file.get('title', 'untitled')
                content = file.get('code', '')
                
                # Check if filename has extension
                has_extension = '.' in filename.split('/')[-1]  # Check last part after any path
                
                if not has_extension:
                    # Add extension based on language (same map as UI)
                    language = file.get('language', '')
                    extension_map = {
                        'python': '.py',
                        'javascript': '.js',
                        'java': '.java',
                        'cpp': '.cpp',
                        'c': '.c',
                        'go': '.go',
                        'rust': '.rs',
                        'php': '.php',
                        'ruby': '.rb',
                        'bash': '.sh'
                    }
                    ext = extension_map.get(language, '.txt')
                    filename += ext
                
                zip_file.writestr(filename, content)
                print(f"[DOWNLOAD] Added to ZIP: {filename}")
        
        # Reset buffer position
        zip_buffer.seek(0)
        
        # Determine ZIP filename
        folder_name = folder_path.replace('/', '_').replace('\\', '_') or 'root'
        zip_filename = f"{folder_name}.zip"
        
        print(f"[DOWNLOAD] ZIP created successfully: {zip_filename}")
        
        # Return as streaming response
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}"
            }
        )
        
    except Exception as e:
        print(f"[ERROR] Failed to create ZIP: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP: {str(e)}"
        )

@router.get("/download/file/{file_id}")
async def download_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Download a single file
    (Optional endpoint - can also be done client-side)
    """
    from bson import ObjectId
    
    db = get_database()
    
    try:
        file = await db.codes.find_one({
            "_id": ObjectId(file_id),
            "user": str(current_user["_id"])
        })
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        filename = file.get('title', 'untitled.txt')
        content = file.get('code', '')
        
        # Return as plain text download
        return StreamingResponse(
            io.BytesIO(content.encode('utf-8')),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        print(f"[ERROR] Download file error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download file")

