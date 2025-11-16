"""Ticket API routes."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field

from models.ticket import Ticket, get_db
from models.user import User
from models.chat import ChatSession, ChatMessage
from services.elsai_service import ElsAIService
from services.image_service import ImageService
from services.ai_chat_service import AIChatService
from services.agent_functions import AgentFunctions
from routes.auth import get_current_user, require_admin


router = APIRouter(prefix="/api", tags=["tickets"])
elsai_service = ElsAIService()
image_service = ImageService()
ai_chat_service = AIChatService()
agent_functions = AgentFunctions()


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
    
    # Calculate ETA based on category
    expected_resolved_datetime = agent_functions.calculate_eta(category)

    # Create ticket in database
    db_ticket = Ticket(
        customer=ticket.customer,
        message=ticket.message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=classification.get("confidence"),
        user_id=current_user.id,
        expected_resolved_datetime=expected_resolved_datetime
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
    
    # Calculate ETA based on category
    expected_resolved_datetime = agent_functions.calculate_eta(category)

    # Create ticket in database
    db_ticket = Ticket(
        customer=customer,
        message=final_message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=classification.get("confidence"),
        screenshot_path=screenshot_path,
        user_id=current_user.id,
        expected_resolved_datetime=expected_resolved_datetime
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


@router.get("/ticket/pending", response_model=List[TicketResponse])
async def get_pending_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get customer's pending tickets for AI agent context.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of pending tickets for the customer
    """
    query = db.query(Ticket).filter(
        Ticket.user_id == current_user.id,
        Ticket.status.in_(["pending", "in_progress"])
    ).order_by(Ticket.created_at.desc())
    
    tickets = query.all()
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


class ChatMessageRequest(BaseModel):
    """Request model for AI chat message."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = None  # If None, create new session


class ChatMessageResponse(BaseModel):
    """Response model for AI chat message."""
    response: str
    status: str
    error: Optional[str] = None
    session_id: int
    message_id: int
    action_performed: Optional[str] = None  # "create_ticket" | "update_category" | "reopen_ticket" | None
    action_details: Optional[Dict[str, Any]] = None


class ChatSessionResponse(BaseModel):
    """Response model for chat session."""
    id: int
    user_id: int
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int


class ChatMessageHistoryResponse(BaseModel):
    """Response model for chat message history."""
    id: int
    session_id: int
    role: str
    content: str
    created_at: str


@router.get("/ai-agent/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all chat sessions for the current user.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of chat sessions
    """
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    
    return [ChatSessionResponse(**session.to_dict()) for session in sessions]


@router.get("/ai-agent/sessions/{session_id}/messages", response_model=List[ChatMessageHistoryResponse])
async def get_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all messages for a specific chat session.
    
    Args:
        session_id: Chat session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of chat messages
    """
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return [ChatMessageHistoryResponse(**msg.to_dict()) for msg in messages]


async def _send_status_event(status: str, message: str = ""):
    """Helper function to send SSE status event."""
    data = json.dumps({"type": "status", "status": status, "message": message})
    return f"data: {data}\n\n"

async def _send_data_event(data: dict):
    """Helper function to send SSE data event."""
    json_data = json.dumps(data)
    return f"data: {json_data}\n\n"


@router.post("/ai-agent/chat/stream")
async def ai_agent_chat_stream(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI Agent chat endpoint with streaming status updates using Server-Sent Events (SSE).
    
    Args:
        request: Chat message request with user query
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        StreamingResponse with status updates and final result
    """
    async def generate():
        # Get database session for this request
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Step 1: Checking database...
            yield await _send_status_event("checking_db", " 🔍 Checking database for your tickets and messages ...")
            await asyncio.sleep(0.3)
            
            # Get or create chat session
            if request.session_id:
                session = db.query(ChatSession).filter(
                    ChatSession.id == request.session_id,
                    ChatSession.user_id == current_user.id
                ).first()
                if not session:
                    yield await _send_data_event({
                        "type": "error",
                        "message": "Chat session not found"
                    })
                    return
            else:
                # Create new session
                yield await _send_status_event("creating_session", " 🔍 Creating chat session for your messages ...")
                await asyncio.sleep(0.2)
                session = ChatSession(
                    user_id=current_user.id,
                    title=request.message[:50] + "..." if len(request.message) > 50 else request.message
                )
                db.add(session)
                db.flush()
            
            # Step 2: Saving user message...
            yield await _send_status_event("saving_message", " 🤖 Saving your message in the database for future reference ...")
            await asyncio.sleep(0.2)
            
            user_message = ChatMessage(
                session_id=session.id,
                role="user",
                content=request.message
            )
            db.add(user_message)
            db.flush()
            
            # Step 3: Fetching tickets...
            yield await _send_status_event("fetching_tickets", " 🔍 Fetching your tickets from the database for context ...")
            await asyncio.sleep(0.3)
            
            query = db.query(Ticket).filter(
                Ticket.user_id == current_user.id,
                Ticket.status.in_(["pending", "in_progress", "resolved"])
            ).order_by(Ticket.created_at.desc())
            
            tickets = query.all()
            ticket_dicts = [ticket.to_dict() for ticket in tickets]
            
            # Step 4: Loading conversation history...
            yield await _send_status_event("loading_history", " 🤖 Loading conversation history from the database for context ...")
            await asyncio.sleep(0.2)
            
            existing_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session.id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in existing_messages[:-1]
            ]
            
            # Step 5: Formatting context...
            yield await _send_status_event("formatting_context", " 🤖 Formatting ticket context for AI agent to understand the context of your tickets ...")
            await asyncio.sleep(0.2)
            
            ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
            
            # Step 6: Finding intent...
            yield await _send_status_event("finding_intent", "🤖 Analyzing your request to understand your intent ...")
            await asyncio.sleep(0.4)
            
            intent = ai_chat_service.detect_action_intent(
                user_query=request.message,
                ticket_context=ticket_context
            )
            
            if intent.get("confidence", 0) < 0.7:
                rule_based_intent = agent_functions.detect_intent(request.message, ticket_dicts)
                if rule_based_intent.get("confidence", 0) > 0.7:
                    intent = rule_based_intent
            
            action_result = None
            action_performed = False
            action_type = None
            action_details = None
            
            # Step 7: Executing action if needed...
            if intent.get("confidence", 0) > 0.7:
                if intent.get("intent") == "create_ticket":
                    yield await _send_status_event("creating_ticket", " 🤖 Creating new ticket...")
                    await asyncio.sleep(0.3)
                    
                    ticket_message = intent.get("ticket_message") or request.message
                    customer_name = current_user.full_name if current_user.full_name else current_user.username
                    
                    yield await _send_status_event("classifying", " 🤖 Classifying ticket...")
                    await asyncio.sleep(0.3)
                    
                    action_result = agent_functions.create_ticket(
                        ticket_message=ticket_message,
                        customer_name=customer_name,
                        user_id=current_user.id,
                        db=db
                    )
                    if action_result.get("success"):
                        action_performed = True
                        action_type = "create_ticket"
                        action_details = {
                            "ticket_id": action_result.get("ticket_id"),
                            "category": action_result.get("category"),
                            "assigned_team": action_result.get("assigned_team"),
                            "status": action_result.get("status"),
                            "eta": action_result.get("eta")
                        }
                        ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                            Ticket.user_id == current_user.id,
                            Ticket.status.in_(["pending", "in_progress", "resolved"])
                        ).order_by(Ticket.created_at.desc()).all()]
                        ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                        action_result = action_result.get("message", "Ticket created successfully")
                
                elif intent.get("intent") == "update_category":
                    yield await _send_status_event("updating_category", "Updating ticket category...")
                    await asyncio.sleep(0.3)
                    
                    ticket_before = db.query(Ticket).filter(
                        Ticket.id == intent["ticket_id"],
                        Ticket.user_id == current_user.id
                    ).first()
                    
                    if ticket_before:
                        action_result = agent_functions.update_ticket_category(
                            ticket_id=intent["ticket_id"],
                            new_category=intent["category"],
                            user_id=current_user.id,
                            db=db
                        )
                        if action_result.get("success"):
                            action_performed = True
                            action_type = "update_category"
                            action_details = {
                                "ticket_id": intent["ticket_id"],
                                "old_category": action_result.get("old_category"),
                                "new_category": action_result.get("new_category"),
                                "old_team": action_result.get("old_team"),
                                "new_team": action_result.get("new_team"),
                                "old_status": action_result.get("old_status"),
                                "new_status": action_result.get("new_status", "pending"),
                                "old_eta": action_result.get("old_eta"),
                                "new_eta": action_result.get("new_eta")
                            }
                            ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                                Ticket.user_id == current_user.id,
                                Ticket.status.in_(["pending", "in_progress", "resolved"])
                            ).order_by(Ticket.created_at.desc()).all()]
                            ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                            action_result = action_result.get("message", "Category updated successfully")
                
                elif intent.get("intent") == "reopen_ticket":
                    yield await _send_status_event("reopening_ticket", " 🤖 Reopening ticket...")
                    await asyncio.sleep(0.3)
                    
                    ticket_before = db.query(Ticket).filter(
                        Ticket.id == intent["ticket_id"],
                        Ticket.user_id == current_user.id
                    ).first()
                    
                    if ticket_before:
                        old_status = ticket_before.status
                        action_result = agent_functions.reopen_ticket(
                            ticket_id=intent["ticket_id"],
                            user_id=current_user.id,
                            db=db
                        )
                        if action_result.get("success"):
                            action_performed = True
                            action_type = "reopen_ticket"
                            action_details = {
                                "ticket_id": intent["ticket_id"],
                                "old_status": old_status,
                                "new_status": "pending"
                            }
                            ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                                Ticket.user_id == current_user.id,
                                Ticket.status.in_(["pending", "in_progress", "resolved"])
                            ).order_by(Ticket.created_at.desc()).all()]
                            ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                            action_result = action_result.get("message", "Ticket reopened successfully")
            
            # Step 8: Generating AI response...
            yield await _send_status_event("generating_response", "Generating AI response...")
            await asyncio.sleep(0.5)
            
            result = ai_chat_service.generate_chat_response(
                user_query=request.message,
                ticket_context=ticket_context,
                conversation_history=conversation_history if conversation_history else None,
                action_result=action_result if action_performed else None
            )
            
            # Step 9: Saving response...
            yield await _send_status_event("saving_response", "Saving response...")
            await asyncio.sleep(0.2)
            
            ai_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=result["response"]
            )
            db.add(ai_message)
            db.flush()
            
            session.updated_at = datetime.utcnow()
            db.commit()
            
            # Send final result
            yield await _send_data_event({
                "type": "complete",
                "response": result["response"],
                "status": result.get("status", "success"),
                "error": result.get("error"),
                "session_id": session.id,
                "message_id": ai_message.id,
                "action_performed": action_type,
                "action_details": action_details
            })
            
        except Exception as e:
            yield await _send_data_event({
                "type": "error",
                "message": str(e)
            })
        finally:
            db.close()
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/ai-agent/chat", response_model=ChatMessageResponse)
async def ai_agent_chat(
    request: ChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    AI Agent chat endpoint that answers questions about customer's tickets.
    Creates or continues a chat session.
    
    Args:
        request: Chat message request with user query
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        AI agent response with session and message IDs
    """
    # Get or create chat session
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
    else:
        # Create new session
        session = ChatSession(
            user_id=current_user.id,
            title=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        db.add(session)
        db.flush()  # Get session ID
    
    # Save user message
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    db.flush()
    
    # Fetch customer's pending tickets
    query = db.query(Ticket).filter(
        Ticket.user_id == current_user.id,
        Ticket.status.in_(["pending", "in_progress", "resolved"])
    ).order_by(Ticket.created_at.desc())
    
    tickets = query.all()
    ticket_dicts = [ticket.to_dict() for ticket in tickets]
    
    # Get conversation history from database
    existing_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in existing_messages[:-1]  # Exclude the message we just added
    ]
    
    # Format ticket context
    ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
    
    # Detect if user wants to perform an action
    # Try AI-based detection first, fallback to rule-based
    intent = ai_chat_service.detect_action_intent(
        user_query=request.message,
        ticket_context=ticket_context
    )
    
    # Fallback to rule-based detection if AI detection confidence is low
    if intent.get("confidence", 0) < 0.7:
        rule_based_intent = agent_functions.detect_intent(request.message, ticket_dicts)
        if rule_based_intent.get("confidence", 0) > 0.7:
            intent = rule_based_intent
    
    action_result = None
    action_performed = False
    action_type = None
    action_details = None
    
    # Execute action if detected with high confidence
    if intent.get("confidence", 0) > 0.7:
        if intent.get("intent") == "create_ticket" and intent.get("ticket_message"):
            # Extract ticket message from intent or use full user message
            ticket_message = intent.get("ticket_message") or request.message
            customer_name = current_user.full_name if current_user.full_name else current_user.username
            
            action_result = agent_functions.create_ticket(
                ticket_message=ticket_message,
                customer_name=customer_name,
                user_id=current_user.id,
                db=db
            )
            if action_result.get("success"):
                action_performed = True
                action_type = "create_ticket"
                action_details = {
                    "ticket_id": action_result.get("ticket_id"),
                    "category": action_result.get("category"),
                    "assigned_team": action_result.get("assigned_team"),
                    "status": action_result.get("status"),
                    "eta": action_result.get("eta")
                }
                # Refresh ticket context after creation
                ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                    Ticket.user_id == current_user.id,
                    Ticket.status.in_(["pending", "in_progress", "resolved"])
                ).order_by(Ticket.created_at.desc()).all()]
                ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                action_result = action_result.get("message", "Ticket created successfully")
        
        elif intent.get("intent") == "update_category" and intent.get("ticket_id") and intent.get("category"):
            # Get ticket before update to capture old values
            ticket_before = db.query(Ticket).filter(
                Ticket.id == intent["ticket_id"],
                Ticket.user_id == current_user.id
            ).first()
            
            if ticket_before:
                action_result = agent_functions.update_ticket_category(
                    ticket_id=intent["ticket_id"],
                    new_category=intent["category"],
                    user_id=current_user.id,
                    db=db
                )
                if action_result.get("success"):
                    action_performed = True
                    action_type = "update_category"
                    action_details = {
                        "ticket_id": intent["ticket_id"],
                        "old_category": action_result.get("old_category"),
                        "new_category": action_result.get("new_category"),
                        "old_team": action_result.get("old_team"),
                        "new_team": action_result.get("new_team"),
                        "old_status": action_result.get("old_status"),
                        "new_status": action_result.get("new_status", "pending"),
                        "old_eta": action_result.get("old_eta"),
                        "new_eta": action_result.get("new_eta")
                    }
                    # Refresh ticket context after update
                    ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                        Ticket.user_id == current_user.id,
                        Ticket.status.in_(["pending", "in_progress", "resolved"])
                    ).order_by(Ticket.created_at.desc()).all()]
                    ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                    action_result = action_result.get("message", "Category updated successfully")
        
        elif intent.get("intent") == "reopen_ticket" and intent.get("ticket_id"):
            # Get ticket before update to capture old status
            ticket_before = db.query(Ticket).filter(
                Ticket.id == intent["ticket_id"],
                Ticket.user_id == current_user.id
            ).first()
            
            if ticket_before:
                old_status = ticket_before.status
                action_result = agent_functions.reopen_ticket(
                    ticket_id=intent["ticket_id"],
                    user_id=current_user.id,
                    db=db
                )
                if action_result.get("success"):
                    action_performed = True
                    action_type = "reopen_ticket"
                    action_details = {
                        "ticket_id": intent["ticket_id"],
                        "old_status": old_status,
                        "new_status": "pending"
                    }
                    # Refresh ticket context after update
                    ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                        Ticket.user_id == current_user.id,
                        Ticket.status.in_(["pending", "in_progress", "resolved"])
                    ).order_by(Ticket.created_at.desc()).all()]
                    ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                    action_result = action_result.get("message", "Ticket reopened successfully")
                else:
                    action_result = action_result.get("error", "Failed to reopen ticket")
    
    # Generate AI response
    result = ai_chat_service.generate_chat_response(
        user_query=request.message,
        ticket_context=ticket_context,
        conversation_history=conversation_history if conversation_history else None,
        action_result=action_result if action_performed else None
    )
    
    # Save AI response
    ai_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["response"]
    )
    db.add(ai_message)
    db.flush()
    
    # Update session updated_at
    session.updated_at = datetime.utcnow()
    
    db.commit()
    
    return ChatMessageResponse(
        response=result["response"],
        status=result.get("status", "success"),
        error=result.get("error"),
        session_id=session.id,
        message_id=ai_message.id,
        action_performed=action_type,
        action_details=action_details
    )


@router.delete("/ai-agent/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: Chat session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    db.delete(session)
    db.commit()
    
    return {"message": "Chat session deleted successfully"}

