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
from services.document_service import DocumentService
from services.ai_chat_service import AIChatService
from services.agent_functions import AgentFunctions
from services.audio_service import AudioService
from services.tts_service import TTSService
from services.email_service import EmailService
from services.knowledge_base_service import KnowledgeBaseService
from routes.auth import get_current_user, require_admin


router = APIRouter(prefix="/api", tags=["tickets"])
elsai_service = ElsAIService()
image_service = ImageService()
document_service = DocumentService()
ai_chat_service = AIChatService()
agent_functions = AgentFunctions()
audio_service = AudioService()
tts_service = TTSService()
email_service = EmailService()
knowledge_base = KnowledgeBaseService()


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

    # Format confidence score to fit database column (max 10 chars)
    confidence_value = classification.get("confidence")
    if confidence_value is not None:
        if isinstance(confidence_value, (int, float)):
            confidence_str = f"{confidence_value:.2f}"
            if len(confidence_str) > 10:
                confidence_str = f"{confidence_value * 100:.1f}%"
            if len(confidence_str) > 10:
                confidence_str = str(confidence_value)[:10]
        else:
            confidence_str = str(confidence_value)[:10]
    else:
        confidence_str = None

    # Create ticket in database
    db_ticket = Ticket(
        customer=ticket.customer,
        message=ticket.message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=confidence_str,
        user_id=current_user.id,
        expected_resolved_datetime=expected_resolved_datetime
    )

    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    
    # Generate voice mail and send email notification
    try:
        eta_str = db_ticket.expected_resolved_datetime.strftime("%Y-%m-%d %H:%M:%S") if db_ticket.expected_resolved_datetime else None
        audio_file_path = tts_service.generate_ticket_created_voicemail(
            ticket_id=db_ticket.id,
            customer_name=ticket.customer,
            category=category,
            assigned_team=assigned_team,
            eta=eta_str
        )
        
        # Send email with voice mail attachment
        if current_user.email:
            email_service.send_ticket_created_email(
                to_email=current_user.email,
                ticket_id=db_ticket.id,
                ticket_message=ticket.message,
                category=category,
                assigned_team=assigned_team,
                customer_name=ticket.customer,
                eta=eta_str,
                audio_file_path=audio_file_path
            )
    except Exception as e:
        print(f"⚠️  Failed to generate/send voice mail for ticket #{db_ticket.id}: {e}")
        import traceback
        traceback.print_exc()

    return TicketResponse(**db_ticket.to_dict())


@router.post("/ticket/chat/stream")
async def create_ticket_with_screenshot_stream(
    message: str = Form(...),
    customer: str = Form(...),
    screenshot: Optional[UploadFile] = File(None),
    session_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Create a ticket with optional screenshot upload (streaming version).
    Provides real-time status updates via Server-Sent Events.
    
    Args:
        message: Ticket message
        customer: Customer name
        screenshot: Optional screenshot file
        session_id: Optional chat session ID to save message to conversation
        current_user: Current authenticated user
        
    Returns:
        StreamingResponse with status updates and final result
    """
    # Read file content immediately (file can only be read once)
    file_content = None
    screenshot_filename = None
    if screenshot:
        try:
            file_content = await screenshot.read()
            screenshot_filename = screenshot.filename
        except Exception as e:
            print(f"⚠️  Error reading file: {e}")
            file_content = None
    
    # Read file content immediately (file can only be read once, must be done before generator)
    file_content = None
    screenshot_filename = None
    if screenshot:
        try:
            file_content = await screenshot.read()
            screenshot_filename = screenshot.filename
        except Exception as e:
            print(f"⚠️  Error reading file: {e}")
            file_content = None
    
    async def generate():
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Step 1: Validating upload
            yield await _send_status_event("validating", "📤 Validating uploaded file...")
            await asyncio.sleep(0.2)
            
            final_message = message
            screenshot_path = None
            
            # Process screenshot if provided
            if screenshot and file_content:
                # Step 2: Processing image
                yield await _send_status_event("processing_image", "🖼️ Processing image...")
                await asyncio.sleep(0.3)
                
                # Step 3: Analyzing image
                yield await _send_status_event("analyzing_image", "🔍 Analyzing image content...")
                image_analysis = document_service.understand_image_content(file_content, screenshot_filename)
                
                # Step 4: Extracting text
                yield await _send_status_event("extracting_text", "📝 Extracting text from image...")
                result = image_service.process_screenshot(file_content, screenshot_filename)
                
                if result.get("error"):
                    yield await _send_data_event({
                        "type": "error",
                        "message": result["error"]
                    })
                    return
                
                screenshot_path = result.get("file_path")
                
                # Build final message with image analysis results
                analysis_parts = []
                
                # Add OCR extracted text if available
                if result.get("extracted_text"):
                    analysis_parts.append(f"[Extracted Text from Screenshot]:\n{result['extracted_text']}")
                
                # Add comprehensive image analysis if available
                if image_analysis:
                    analysis_text = "[Image Analysis]:\n"
                    if image_analysis.get("description"):
                        analysis_text += f"Description: {image_analysis.get('description')}\n"
                    if image_analysis.get("issues"):
                        analysis_text += f"Issues Detected: {', '.join(image_analysis.get('issues', []))}\n"
                    if image_analysis.get("suggested_category"):
                        analysis_text += f"Suggested Category: {image_analysis.get('suggested_category')}\n"
                    if image_analysis.get("reason"):
                        analysis_text += f"Reason: {image_analysis.get('reason')}\n"
                    if image_analysis.get("severity"):
                        analysis_text += f"Severity: {image_analysis.get('severity')}\n"
                    analysis_parts.append(analysis_text.strip())
                
                # Combine all analysis into final message
                if analysis_parts:
                    final_message = f"{message}\n\n" + "\n\n".join(analysis_parts)
            
            # Step 5: Classifying ticket
            yield await _send_status_event("classifying", "🤖 Classifying ticket...")
            await asyncio.sleep(0.3)
            
            classification = elsai_service.classify_ticket(final_message)
            category = classification["label"]
            assigned_team = elsai_service.get_assigned_team(category)
            
            # Step 6: Calculating ETA
            yield await _send_status_event("calculating_eta", "⏱️ Calculating estimated resolution time...")
            await asyncio.sleep(0.2)
            
            expected_resolved_datetime = agent_functions.calculate_eta(category)
            
            # Format confidence score
            confidence_value = classification.get("confidence")
            if confidence_value is not None:
                if isinstance(confidence_value, (int, float)):
                    confidence_str = f"{confidence_value:.2f}"
                    if len(confidence_str) > 10:
                        confidence_str = f"{confidence_value * 100:.1f}%"
                    if len(confidence_str) > 10:
                        confidence_str = str(confidence_value)[:10]
                else:
                    confidence_str = str(confidence_value)[:10]
            else:
                confidence_str = None
            
            # Step 7: Saving to conversation
            yield await _send_status_event("saving_conversation", "💬 Saving to conversation...")
            await asyncio.sleep(0.2)
            
            chat_message_id = None
            actual_session_id = session_id
            session = None
            
            try:
                if session_id:
                    session = db.query(ChatSession).filter(
                        ChatSession.id == session_id,
                        ChatSession.user_id == current_user.id
                    ).first()
                    if not session:
                        session = ChatSession(
                            user_id=current_user.id,
                            title=f"Image upload: {screenshot_filename if screenshot_filename else 'document'}"
                        )
                        db.add(session)
                        db.flush()
                        actual_session_id = session.id
                else:
                    session = ChatSession(
                        user_id=current_user.id,
                        title=f"Image upload: {screenshot_filename if screenshot_filename else 'document'}"
                    )
                    db.add(session)
                    db.flush()
                    actual_session_id = session.id
                
                if session and session.id:
                    upload_message_content = f"📎 I uploaded an image: {screenshot_filename if screenshot_filename else 'document'}"
                    if message and message.strip() and message != f"I uploaded an image: {screenshot_filename if screenshot_filename else 'document'}":
                        upload_message_content += f"\n\n{message}"
                    
                    user_message = ChatMessage(
                        session_id=session.id,
                        role="user",
                        content=upload_message_content
                    )
                    db.add(user_message)
                    db.flush()
                    chat_message_id = user_message.id
                    
                    session.updated_at = datetime.utcnow()
                    db.flush()
            except Exception as e:
                print(f"⚠️  Error saving conversation: {e}")
            
            # Step 8: Creating ticket
            yield await _send_status_event("creating_ticket", "🎫 Creating ticket in database...")
            await asyncio.sleep(0.3)
            
            db_ticket = Ticket(
                customer=customer,
                message=final_message,
                category=category,
                assigned_team=assigned_team,
                status="pending",
                confidence=confidence_str,
                screenshot_path=screenshot_path,
                user_id=current_user.id,
                expected_resolved_datetime=expected_resolved_datetime
            )
            
            db.add(db_ticket)
            db.flush()
            
            # Step 9: Generating AI response
            ai_response_message = None
            if session and session.id and chat_message_id:
                yield await _send_status_event("generating_response", "🤖 Generating AI response...")
                await asyncio.sleep(0.2)
                
                try:
                    ticket_info = f"Ticket #{db_ticket.id} has been created"
                    if category:
                        ticket_info += f" and categorized as '{category}'"
                    if assigned_team:
                        ticket_info += f" (assigned to {assigned_team})"
                    
                    ai_response_message = ChatMessage(
                        session_id=session.id,
                        role="assistant",
                        content=f"✅ {ticket_info}. The image has been analyzed and the ticket is now in the system. How can I help you further?"
                    )
                    db.add(ai_response_message)
                    db.flush()
                    
                    session.updated_at = datetime.utcnow()
                except Exception as e:
                    print(f"⚠️  Error creating AI response: {e}")
            
            # Step 10: Committing changes
            yield await _send_status_event("committing", "💾 Saving all changes...")
            await asyncio.sleep(0.2)
            
            db.commit()
            db.refresh(db_ticket)
            
            if ai_response_message:
                db.refresh(ai_response_message)
            if session:
                db.refresh(session)
            
            # Step 11: Sending notifications (async, don't wait)
            yield await _send_status_event("sending_notifications", "📧 Sending email notification...")
            
            # Send notifications in background (don't block)
            try:
                eta_str = db_ticket.expected_resolved_datetime.strftime("%Y-%m-%d %H:%M:%S") if db_ticket.expected_resolved_datetime else None
                audio_file_path = tts_service.generate_ticket_created_voicemail(
                    ticket_id=db_ticket.id,
                    customer_name=customer,
                    category=category,
                    assigned_team=assigned_team,
                    eta=eta_str
                )
                
                if current_user.email:
                    email_service.send_ticket_created_email(
                        to_email=current_user.email,
                        ticket_id=db_ticket.id,
                        ticket_message=final_message,
                        category=category,
                        assigned_team=assigned_team,
                        customer_name=customer,
                        eta=eta_str,
                        audio_file_path=audio_file_path
                    )
            except Exception as e:
                print(f"⚠️  Failed to send notifications: {e}")
            
            # Final result
            ticket_dict = db_ticket.to_dict()
            if actual_session_id and chat_message_id:
                ticket_dict["session_id"] = actual_session_id
                ticket_dict["message_id"] = chat_message_id
                if ai_response_message:
                    ticket_dict["ai_message_id"] = ai_response_message.id
            
            yield await _send_data_event({
                "type": "complete",
                "ticket": ticket_dict,
                "session_id": actual_session_id,
                "message_id": chat_message_id,
                "ai_message_id": ai_response_message.id if ai_response_message else None
            })
            
        except Exception as e:
            yield await _send_data_event({
                "type": "error",
                "message": str(e)
            })
            import traceback
            traceback.print_exc()
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


@router.post("/ticket/chat", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_with_screenshot(
    message: str = Form(...),
    customer: str = Form(...),
    screenshot: Optional[UploadFile] = File(None),
    session_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a ticket with optional screenshot upload (for chatbot interface).
    Optionally saves upload message to chat session.

    Args:
        message: Ticket message
        customer: Customer name
        screenshot: Optional screenshot file
        session_id: Optional chat session ID to save message to conversation
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
        
        # Get comprehensive image analysis using vision model
        image_analysis = document_service.understand_image_content(file_content, screenshot.filename)
        
        # Also process screenshot for saving and OCR text extraction
        result = image_service.process_screenshot(file_content, screenshot.filename)
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        screenshot_path = result.get("file_path")
        
        # Build final message with image analysis results
        analysis_parts = []
        
        # Add OCR extracted text if available
        if result.get("extracted_text"):
            analysis_parts.append(f"[Extracted Text from Screenshot]:\n{result['extracted_text']}")
        
        # Add comprehensive image analysis if available
        if image_analysis:
            analysis_text = "[Image Analysis]:\n"
            if image_analysis.get("description"):
                analysis_text += f"Description: {image_analysis.get('description')}\n"
            if image_analysis.get("issues"):
                analysis_text += f"Issues Detected: {', '.join(image_analysis.get('issues', []))}\n"
            if image_analysis.get("suggested_category"):
                analysis_text += f"Suggested Category: {image_analysis.get('suggested_category')}\n"
            if image_analysis.get("reason"):
                analysis_text += f"Reason: {image_analysis.get('reason')}\n"
            if image_analysis.get("severity"):
                analysis_text += f"Severity: {image_analysis.get('severity')}\n"
            analysis_parts.append(analysis_text.strip())
        
        # Combine all analysis into final message
        if analysis_parts:
            final_message = f"{message}\n\n" + "\n\n".join(analysis_parts)
    
    # Classify ticket using ElsAI NLI
    classification = elsai_service.classify_ticket(final_message)
    category = classification["label"]
    assigned_team = elsai_service.get_assigned_team(category)
    
    # Calculate ETA based on category
    expected_resolved_datetime = agent_functions.calculate_eta(category)

    # Format confidence score to fit database column (max 10 chars)
    confidence_value = classification.get("confidence")
    if confidence_value is not None:
        if isinstance(confidence_value, (int, float)):
            confidence_str = f"{confidence_value:.2f}"
            if len(confidence_str) > 10:
                confidence_str = f"{confidence_value * 100:.1f}%"
            if len(confidence_str) > 10:
                confidence_str = str(confidence_value)[:10]
        else:
            confidence_str = str(confidence_value)[:10]
    else:
        confidence_str = None

    # Save upload message to chat session - create session if needed
    chat_message_id = None
    actual_session_id = session_id
    session = None
    
    try:
        if session_id:
            # Use existing session
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            ).first()
            if not session:
                # Session not found, create new one
                session = ChatSession(
                    user_id=current_user.id,
                    title=f"Image upload: {screenshot.filename if screenshot else 'document'}"
                )
                db.add(session)
                db.flush()
                actual_session_id = session.id
        else:
            # Create new session for upload
            session = ChatSession(
                user_id=current_user.id,
                title=f"Image upload: {screenshot.filename if screenshot else 'document'}"
            )
            db.add(session)
            db.flush()
            actual_session_id = session.id
        
        # Create user message about the upload
        if session and session.id:
            upload_message_content = f"📎 I uploaded an image: {screenshot.filename if screenshot else 'document'}"
            if message and message.strip() and message != f"I uploaded an image: {screenshot.filename if screenshot else 'document'}":
                upload_message_content += f"\n\n{message}"
            
            user_message = ChatMessage(
                session_id=session.id,
                role="user",
                content=upload_message_content
            )
            db.add(user_message)
            db.flush()
            chat_message_id = user_message.id
            
            # Update session timestamp
            session.updated_at = datetime.utcnow()
            db.flush()  # Ensure session update is saved
    except Exception as e:
        print(f"⚠️  Error saving conversation: {e}")
        import traceback
        traceback.print_exc()
        # Continue with ticket creation even if conversation save fails
    
    # Create ticket in database
    db_ticket = Ticket(
        customer=customer,
        message=final_message,
        category=category,
        assigned_team=assigned_team,
        status="pending",
        confidence=confidence_str,
        screenshot_path=screenshot_path,
        user_id=current_user.id,
        expected_resolved_datetime=expected_resolved_datetime
    )

    db.add(db_ticket)
    db.flush()  # Flush to get ticket ID before creating AI response
    
    # Generate AI response about the upload if session exists
    ai_response_message = None
    if session and session.id and chat_message_id:
        try:
            # Create a helpful AI response about the ticket creation
            ticket_info = f"Ticket #{db_ticket.id} has been created"
            if category:
                ticket_info += f" and categorized as '{category}'"
            if assigned_team:
                ticket_info += f" (assigned to {assigned_team})"
            
            ai_response_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=f"✅ {ticket_info}. The image has been analyzed and the ticket is now in the system. How can I help you further?"
            )
            db.add(ai_response_message)
            db.flush()  # Flush AI message before commit
            
            # Update session timestamp again
            session.updated_at = datetime.utcnow()
        except Exception as e:
            print(f"⚠️  Error creating AI response message: {e}")
            import traceback
            traceback.print_exc()
            ai_response_message = None
    
    # Commit both ticket and chat messages together
    try:
        db.commit()
        db.refresh(db_ticket)
        
        # Refresh AI message to get its ID after commit
        if ai_response_message:
            db.refresh(ai_response_message)
        
        # Refresh session to ensure it's updated
        if session:
            db.refresh(session)
    except Exception as e:
        print(f"⚠️  Error committing conversation: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    
    # Generate voice mail and send email notification
    try:
        eta_str = db_ticket.expected_resolved_datetime.strftime("%Y-%m-%d %H:%M:%S") if db_ticket.expected_resolved_datetime else None
        audio_file_path = tts_service.generate_ticket_created_voicemail(
            ticket_id=db_ticket.id,
            customer_name=customer,
            category=category,
            assigned_team=assigned_team,
            eta=eta_str
        )
        
        # Send email with voice mail attachment
        if current_user.email:
            email_service.send_ticket_created_email(
                to_email=current_user.email,
                ticket_id=db_ticket.id,
                ticket_message=final_message,
                category=category,
                assigned_team=assigned_team,
                customer_name=customer,
                eta=eta_str,
                audio_file_path=audio_file_path
            )
    except Exception as e:
        print(f"⚠️  Failed to generate/send voice mail for ticket #{db_ticket.id}: {e}")
        import traceback
        traceback.print_exc()

    ticket_dict = db_ticket.to_dict()
    # Add session info if message was saved to conversation
    if actual_session_id and chat_message_id:
        ticket_dict["session_id"] = actual_session_id
        ticket_dict["message_id"] = chat_message_id
        if ai_response_message:
            ticket_dict["ai_message_id"] = ai_response_message.id
    
    return TicketResponse(**ticket_dict)


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
    audio_file_path: Optional[str] = None
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
    
    # Debug logging
    print(f"📨 Retrieved {len(messages)} messages for session {session_id}")
    for msg in messages:
        print(f"  - Message {msg.id}: {msg.role} - {msg.content[:50] if msg.content else 'empty'}...")
    
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
            
            # Step 5.5: Search knowledge base for relevant documents (RAG)
            yield await _send_status_event("searching_kb", " 🔍 Searching knowledge base for relevant information...")
            await asyncio.sleep(0.3)
            
            knowledge_base_context = knowledge_base.get_context_for_query(
                query=request.message,
                top_k=3,
                min_similarity=0.5
            )
            
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
                        old_category = ticket_before.category
                        old_team = ticket_before.assigned_team
                        
                        # Check if category is mentioned in the intent (from AI detection)
                        new_category = intent.get("category")
                        
                        action_result = agent_functions.reopen_ticket(
                            ticket_id=intent["ticket_id"],
                            user_id=current_user.id,
                            db=db,
                            new_category=new_category
                        )
                        if action_result.get("success"):
                            action_performed = True
                            action_type = "reopen_ticket"
                            action_details = {
                                "ticket_id": intent["ticket_id"],
                                "old_status": old_status,
                                "new_status": "pending",
                                "category_updated": action_result.get("category_updated", False),
                                "old_category": action_result.get("old_category"),
                                "new_category": action_result.get("new_category"),
                                "old_team": action_result.get("old_team"),
                                "new_team": action_result.get("new_team")
                            }
                            ticket_dicts = [t.to_dict() for t in db.query(Ticket).filter(
                                Ticket.user_id == current_user.id,
                                Ticket.status.in_(["pending", "in_progress", "resolved"])
                            ).order_by(Ticket.created_at.desc()).all()]
                            ticket_context = ai_chat_service.format_ticket_context(ticket_dicts)
                            action_result = action_result.get("message", "Ticket reopened successfully")
            
            # Step 7.5: Check if user is asking about document/image analysis
            document_analysis_context = None
            analysis_keywords = ["analyze", "analysis", "what information", "what's in", "tell me about", "describe", "what does"]
            user_query_lower = request.message.lower()
            
            if any(keyword in user_query_lower for keyword in analysis_keywords) and any(word in user_query_lower for word in ["document", "image", "screenshot", "file", "upload"]):
                yield await _send_status_event("analyzing_document", " 🔍 Analyzing uploaded document/image...")
                await asyncio.sleep(0.3)
                
                # Find most recent ticket with screenshot/document
                recent_ticket_with_screenshot = db.query(Ticket).filter(
                    Ticket.user_id == current_user.id,
                    Ticket.screenshot_path.isnot(None)
                ).order_by(Ticket.created_at.desc()).first()
                
                if recent_ticket_with_screenshot:
                    ticket_message = recent_ticket_with_screenshot.message
                    
                    # Extract image analysis from ticket message
                    if "[Image Analysis]:" in ticket_message or "[Extracted Text from Screenshot]:" in ticket_message:
                        # Extract the analysis section
                        analysis_sections = []
                        if "[Extracted Text from Screenshot]:" in ticket_message:
                            extracted_start = ticket_message.find("[Extracted Text from Screenshot]:")
                            extracted_end = ticket_message.find("[Image Analysis]:", extracted_start)
                            if extracted_end == -1:
                                extracted_end = len(ticket_message)
                            extracted_text = ticket_message[extracted_start:extracted_end].strip()
                            analysis_sections.append(extracted_text)
                        
                        if "[Image Analysis]:" in ticket_message:
                            analysis_start = ticket_message.find("[Image Analysis]:")
                            analysis_text = ticket_message[analysis_start:].strip()
                            analysis_sections.append(analysis_text)
                        
                        if analysis_sections:
                            document_analysis_context = "\n\n".join(analysis_sections)
                            document_analysis_context += f"\n\nDocument File: {recent_ticket_with_screenshot.screenshot_path}"
            
            # Step 8: Generating AI response...
            yield await _send_status_event("generating_response", "Generating AI response...")
            await asyncio.sleep(0.5)
            
            result = ai_chat_service.generate_chat_response(
                user_query=request.message,
                ticket_context=ticket_context,
                conversation_history=conversation_history if conversation_history else None,
                action_result=action_result if action_performed else None,
                knowledge_base_context=knowledge_base_context if knowledge_base_context else None,
                document_analysis_context=document_analysis_context
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
                old_category = ticket_before.category
                old_team = ticket_before.assigned_team
                
                # Check if category is mentioned in the intent (from AI detection)
                new_category = intent.get("category")
                
                action_result = agent_functions.reopen_ticket(
                    ticket_id=intent["ticket_id"],
                    user_id=current_user.id,
                    db=db,
                    new_category=new_category
                )
                if action_result.get("success"):
                    action_performed = True
                    action_type = "reopen_ticket"
                    action_details = {
                        "ticket_id": intent["ticket_id"],
                        "old_status": old_status,
                        "new_status": "pending",
                        "category_updated": action_result.get("category_updated", False),
                        "old_category": action_result.get("old_category"),
                        "new_category": action_result.get("new_category"),
                        "old_team": action_result.get("old_team"),
                        "new_team": action_result.get("new_team")
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
    
    # Check if user is asking about document/image analysis
    document_analysis_context = None
    analysis_keywords = ["analyze", "analysis", "what information", "what's in", "tell me about", "describe", "what does"]
    user_query_lower = request.message.lower()
    
    if any(keyword in user_query_lower for keyword in analysis_keywords) and any(word in user_query_lower for word in ["document", "image", "screenshot", "file", "upload"]):
        # Find most recent ticket with screenshot/document
        recent_ticket_with_screenshot = db.query(Ticket).filter(
            Ticket.user_id == current_user.id,
            Ticket.screenshot_path.isnot(None)
        ).order_by(Ticket.created_at.desc()).first()
        
        if recent_ticket_with_screenshot:
            ticket_message = recent_ticket_with_screenshot.message
            
            # Extract image analysis from ticket message
            if "[Image Analysis]:" in ticket_message or "[Extracted Text from Screenshot]:" in ticket_message:
                # Extract the analysis section
                analysis_sections = []
                if "[Extracted Text from Screenshot]:" in ticket_message:
                    extracted_start = ticket_message.find("[Extracted Text from Screenshot]:")
                    extracted_end = ticket_message.find("[Image Analysis]:", extracted_start)
                    if extracted_end == -1:
                        extracted_end = len(ticket_message)
                    extracted_text = ticket_message[extracted_start:extracted_end].strip()
                    analysis_sections.append(extracted_text)
                
                if "[Image Analysis]:" in ticket_message:
                    analysis_start = ticket_message.find("[Image Analysis]:")
                    analysis_text = ticket_message[analysis_start:].strip()
                    analysis_sections.append(analysis_text)
                
                if analysis_sections:
                    document_analysis_context = "\n\n".join(analysis_sections)
                    document_analysis_context += f"\n\nDocument File: {recent_ticket_with_screenshot.screenshot_path}"
    
    # Generate AI response
    result = ai_chat_service.generate_chat_response(
        user_query=request.message,
        ticket_context=ticket_context,
        conversation_history=conversation_history if conversation_history else None,
        action_result=action_result if action_performed else None,
        document_analysis_context=document_analysis_context
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


@router.post("/ai-agent/document/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a document (image, PDF, DOCX) for OCR and knowledge base storage.
    
    Args:
        file: Document file to upload
        session_id: Optional chat session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Document processing result with extracted text and metadata
    """
    try:
        # Validate file type
        content_type = file.content_type or ""
        supported_types = (
            ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/tiff'] +
            ['application/pdf'] +
            ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        )
        
        if content_type not in supported_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}. Supported types: images, PDF, DOCX"
            )
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # Get or create session
        if session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            ).first()
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found"
                )
        else:
            session = ChatSession(
                user_id=current_user.id,
                title=f"Document: {file.filename}"
            )
            db.add(session)
            db.flush()
        
        # Process document and add to knowledge base
        result = knowledge_base.add_document(
            file_content=file_content,
            filename=file.filename or "document",
            content_type=content_type,
            session_id=session.id,
            metadata={
                "uploaded_by": current_user.username,
                "user_id": current_user.id
            }
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to process document")
            )
        
        # Check if image understanding suggests creating a ticket
        image_understanding = result.get("image_understanding")
        auto_create_ticket = False
        ticket_info = None
        
        if image_understanding and content_type.startswith('image/'):
            suggested_category = image_understanding.get("suggested_category")
            description = image_understanding.get("description", "")
            issues = image_understanding.get("issues", [])
            
            # Auto-create ticket if image shows a clear issue
            if suggested_category and (issues or "broken" in description.lower() or "damage" in description.lower() or "error" in description.lower()):
                auto_create_ticket = True
                
                # Create ticket message from image understanding
                ticket_message = f"Product Issue Reported via Image:\n\n"
                ticket_message += f"Description: {description}\n"
                if issues:
                    ticket_message += f"Issues: {', '.join(issues)}\n"
                ticket_message += f"Severity: {image_understanding.get('severity', 'medium')}"
                
                # Create ticket automatically with suggested category
                try:
                    customer_name = current_user.full_name if current_user.full_name else current_user.username
                    
                    # Use image-understood category directly, or let create_ticket classify
                    # For now, let create_ticket classify (it will likely match the suggestion)
                    ticket_result = agent_functions.create_ticket(
                        ticket_message=ticket_message,
                        customer_name=customer_name,
                        user_id=current_user.id,
                        db=db
                    )
                    
                    # If classification doesn't match suggestion, update it
                    if ticket_result.get("success") and suggested_category:
                        final_category = ticket_result.get("category", "").lower()
                        if final_category != suggested_category.lower():
                            # Update category to match image understanding
                            update_result = agent_functions.update_ticket_category(
                                ticket_id=ticket_result.get("ticket_id"),
                                new_category=suggested_category,
                                user_id=current_user.id,
                                db=db
                            )
                            if update_result.get("success"):
                                ticket_result["category"] = suggested_category
                                ticket_result["assigned_team"] = update_result.get("new_team")
                                ticket_result["message"] = f"Ticket #{ticket_result.get('ticket_id')} created and categorized as {suggested_category} based on image analysis."
                    
                    if ticket_result.get("success"):
                        ticket_info = {
                            "ticket_id": ticket_result.get("ticket_id"),
                            "category": ticket_result.get("category"),
                            "assigned_team": ticket_result.get("assigned_team"),
                            "status": ticket_result.get("status"),
                            "message": ticket_result.get("message")
                        }
                except Exception as e:
                    print(f"⚠️  Failed to auto-create ticket from image: {e}")
                    auto_create_ticket = False
        
        # Create user message about document upload
        upload_message = f"[Document uploaded: {file.filename}]"
        if auto_create_ticket and ticket_info:
            upload_message += f"\n✅ Ticket #{ticket_info['ticket_id']} automatically created ({ticket_info['category']} - {ticket_info['assigned_team']})"
        
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=upload_message
        )
        db.add(user_message)
        db.flush()
        
        session.updated_at = datetime.utcnow()
        db.commit()
        
        response_data = {
            "success": True,
            "document_id": result.get("document_id"),
            "file_path": result.get("file_path"),
            "file_type": result.get("file_type"),
            "extracted_text_preview": result.get("extracted_text"),
            "text_length": result.get("text_length"),
            "session_id": session.id,
            "message_id": user_message.id,
            "image_understanding": image_understanding,
            "message": f"Document '{file.filename}' processed and added to knowledge base. {result.get('text_length', 0)} characters extracted."
        }
        
        if auto_create_ticket and ticket_info:
            response_data["ticket_created"] = True
            response_data["ticket_info"] = ticket_info
            response_data["message"] += f" Ticket #{ticket_info['ticket_id']} automatically created for this issue."
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )


@router.post("/ai-agent/audio/upload")
async def upload_audio_file(
    audio: UploadFile = File(...),
    session_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload audio file, convert to text, and process as chat message.
    
    Args:
        audio: Audio file (MP3 preferred)
        session_id: Optional chat session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Dictionary with transcribed text, audio file path, and session info
    """
    try:
        # Validate file type
        if not audio.content_type or not audio.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file"
            )
        
        # Read audio file content
        file_content = await audio.read()
        
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio file is empty"
            )
        
        # Validate session if provided
        if session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == current_user.id
            ).first()
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Chat session not found"
                )
        else:
            # Create new session for audio message
            session = ChatSession(
                user_id=current_user.id,
                title="Voice Message"
            )
            db.add(session)
            db.flush()
        
        # Process audio: save and convert to text
        result = audio_service.process_audio_upload(
            file_content=file_content,
            filename=audio.filename or "audio.mp3",
            session_id=session.id
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to process audio")
            )
        
        transcribed_text = result.get("text", "")
        audio_file_path = result.get("audio_file_path")
        stt_error = result.get("error")  # May contain STT error even if file saved
        
        # Save user message with audio file path
        # Use transcribed text if available, otherwise use placeholder
        message_content = transcribed_text if transcribed_text else "[Voice message - transcription unavailable. Please install ffmpeg for speech-to-text conversion.]"
        
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=message_content,
            audio_file_path=audio_file_path
        )
        db.add(user_message)
        db.flush()
        
        # Update session
        session.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "text": transcribed_text,
            "audio_file_path": audio_file_path,
            "session_id": session.id,
            "message_id": user_message.id,
            "error": stt_error if not transcribed_text else None,
            "warning": stt_error if stt_error and transcribed_text else None  # Warning if STT had issues but file saved
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing audio: {str(e)}"
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

