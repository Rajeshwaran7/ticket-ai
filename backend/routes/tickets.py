"""Ticket API routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field

from models.ticket import Ticket, get_db
from models.user import User
from services.elsai_service import ElsAIService
from services.image_service import ImageService
from routes.auth import get_current_user, require_admin


router = APIRouter(prefix="/api", tags=["tickets"])
elsai_service = ElsAIService()
image_service = ImageService()


class TicketCreate(BaseModel):
    """Request model for creating a ticket."""
    customer: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)


class TicketUpdate(BaseModel):
    """Request model for updating ticket status."""
    status: str = Field(..., pattern="^(pending|in_progress|resolved|closed)$")


class TicketResponse(BaseModel):
    """Response model for ticket."""
    id: int
    customer: str
    message: str
    category: str
    assignedTeam: str
    status: str
    createdAt: str
    confidence: Optional[str] = None
    screenshot_path: Optional[str] = None
    user_id: Optional[int] = None


class ClassifyRequest(BaseModel):
    """Request model for classification."""
    text: str = Field(..., min_length=1, max_length=5000)


class ClassifyResponse(BaseModel):
    """Response model for classification."""
    label: str
    confidence: str
    assignedTeam: str
    error: Optional[str] = None


@router.post("/classify", response_model=ClassifyResponse)
async def classify_ticket(request: ClassifyRequest):
    """
    Classify ticket text using ElsAI NLI API.

    Args:
        request: Classification request with text

    Returns:
        Classification result with label, confidence, and assigned team
    """
    result = elsai_service.classify_ticket(request.text)
    assigned_team = elsai_service.get_assigned_team(result["label"])

    return ClassifyResponse(
        label=result["label"],
        confidence=result["confidence"],
        assignedTeam=assigned_team,
        error=result.get("error")
    )


@router.post("/ticket", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new ticket with automatic classification and routing.

    Args:
        ticket: Ticket creation request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created ticket with classification results
    """
    # Classify ticket using ElsAI NLI
    classification = elsai_service.classify_ticket(ticket.message)
    category = classification["label"]
    assigned_team = elsai_service.get_assigned_team(category)

    # Create ticket in database
    db_ticket = Ticket(
        customer=ticket.customer,
        message=ticket.message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=classification.get("confidence"),
        user_id=current_user.id
    )

    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    return TicketResponse(**db_ticket.to_dict())


@router.post("/ticket/chat", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_with_screenshot(
    message: str = Form(...),
    customer: str = Form(...),
    screenshot: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a ticket with optional screenshot upload (for chatbot interface).

    Args:
        message: Ticket message
        customer: Customer name
        screenshot: Optional screenshot file
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created ticket with classification results
    """
    final_message = message
    screenshot_path = None
    
    # Process screenshot if provided
    if screenshot:
        file_content = await screenshot.read()
        result = image_service.process_screenshot(file_content, screenshot.filename)
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        screenshot_path = result.get("file_path")
        
        # Append extracted text to message if available
        if result.get("extracted_text"):
            final_message = f"{message}\n\n[Extracted from screenshot]:\n{result['extracted_text']}"
    
    # Classify ticket using ElsAI NLI
    classification = elsai_service.classify_ticket(final_message)
    category = classification["label"]
    assigned_team = elsai_service.get_assigned_team(category)

    # Create ticket in database
    db_ticket = Ticket(
        customer=customer,
        message=final_message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=classification.get("confidence"),
        screenshot_path=screenshot_path,
        user_id=current_user.id
    )

    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)

    return TicketResponse(**db_ticket.to_dict())


@router.get("/ticket", response_model=List[TicketResponse])
async def get_tickets(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get tickets with pagination, search, and filters.
    Customers see only their tickets, admins see all.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        search: Search term for customer name or message
        category: Filter by category
        status_filter: Filter by status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of tickets
    """
    query = db.query(Ticket)
    
    # Filter by user role
    if current_user.role.value == "customer":
        query = query.filter(Ticket.user_id == current_user.id)
    
    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Ticket.customer.ilike(search_term),
                Ticket.message.ilike(search_term)
            )
        )
    
    # Apply category filter
    if category:
        query = query.filter(Ticket.category == category)
    
    # Apply status filter
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    
    # Order by created_at descending
    query = query.order_by(Ticket.created_at.desc())
    
    # Apply pagination
    tickets = query.offset(skip).limit(limit).all()
    return [TicketResponse(**ticket.to_dict()) for ticket in tickets]


@router.get("/ticket/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific ticket by ID.

    Args:
        ticket_id: Ticket ID
        db: Database session

    Returns:
        Ticket details
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found"
        )
    return TicketResponse(**ticket.to_dict())


@router.put("/ticket/{ticket_id}/status", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: int,
    update: TicketUpdate,
    db: Session = Depends(get_db)
):
    """
    Update ticket status.

    Args:
        ticket_id: Ticket ID
        update: Status update request
        db: Database session

    Returns:
        Updated ticket
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with id {ticket_id} not found"
        )

    ticket.status = update.status
    db.commit()
    db.refresh(ticket)

    return TicketResponse(**ticket.to_dict())

