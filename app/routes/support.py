"""
Support Ticket Routes
Handles support ticket submissions and management
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
import uuid

# Import database connection
from app.database import get_database

router = APIRouter()

# ============================================================================
# MODELS
# ============================================================================

class SupportTicketCreate(BaseModel):
    """Support ticket creation model"""
    name: str
    email: EmailStr
    subject: str
    category: str  # technical, account, feature, bug, interview, other
    priority: str = "medium"  # low, medium, high
    message: str
    user_id: Optional[str] = None
    username: Optional[str] = None

class SupportTicketResponse(BaseModel):
    """Support ticket response model"""
    ticket_id: str
    status: str
    message: str

# ============================================================================
# ROUTES
# ============================================================================

@router.post("/ticket", response_model=SupportTicketResponse)
async def create_support_ticket(ticket: SupportTicketCreate):
    """
    Create a new support ticket
    
    Args:
        ticket: Support ticket data
    
    Returns:
        SupportTicketResponse with ticket ID
    """
    try:
        # Get database connection
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        # Generate ticket ID
        ticket_id = f"TICKET-{str(uuid.uuid4())[:8].upper()}"
        
        # Create ticket document
        ticket_doc = {
            "ticket_id": ticket_id,
            "name": ticket.name,
            "email": ticket.email,
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "message": ticket.message,
            "user_id": ticket.user_id,
            "username": ticket.username,
            "status": "open",  # open, in_progress, resolved, closed
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "assigned_to": None,
            "resolution": None,
            "resolved_at": None,
            "notes": []
        }
        
        # Insert into database
        result = await db.support_tickets.insert_one(ticket_doc)
        
        if result.inserted_id:
            return SupportTicketResponse(
                ticket_id=ticket_id,
                status="success",
                message=f"Support ticket {ticket_id} created successfully. We'll get back to you within 24-48 hours."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create support ticket"
            )
            
    except Exception as e:
        print(f"Error creating support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the support ticket: {str(e)}"
        )


@router.get("/tickets/{ticket_id}")
async def get_support_ticket(ticket_id: str):
    """
    Get support ticket by ID
    
    Args:
        ticket_id: Ticket ID
    
    Returns:
        Support ticket details
    """
    try:
        # Get database connection
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        ticket = await db.support_tickets.find_one(
            {"ticket_id": ticket_id},
            {"_id": 0}
        )
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found"
            )
        
        return ticket
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving support ticket: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the support ticket"
        )


@router.get("/tickets/email/{email}")
async def get_user_tickets(email: str, limit: int = 20):
    """
    Get all tickets for a user by email
    
    Args:
        email: User email
        limit: Maximum number of tickets to return
    
    Returns:
        List of support tickets
    """
    try:
        # Get database connection
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection not available"
            )
        
        cursor = db.support_tickets.find(
            {"email": email},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        tickets = await cursor.to_list(length=limit)
        
        return {
            "email": email,
            "count": len(tickets),
            "tickets": tickets
        }
        
    except Exception as e:
        print(f"Error retrieving user tickets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving tickets"
        )


# ============================================================================
# ADMIN ROUTES (Future Implementation)
# ============================================================================

# These routes would be for admin panel to manage support tickets
# Can be added later as needed:
# - GET /admin/tickets (list all tickets)
# - PUT /tickets/{ticket_id}/status (update ticket status)
# - PUT /tickets/{ticket_id}/assign (assign to team member)
# - POST /tickets/{ticket_id}/notes (add internal notes)
# - PUT /tickets/{ticket_id}/resolve (mark as resolved)

