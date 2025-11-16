"""Agent functions for ticket management actions."""
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

from models.ticket import Ticket
from models.user import User
from services.elsai_service import ElsAIService
from services.tts_service import TTSService
from services.email_service import EmailService

elsai_service = ElsAIService()
tts_service = TTSService()
email_service = EmailService()


class AgentFunctions:
    """Agent functions for detecting and executing ticket management actions."""

    def __init__(self):
        """Initialize agent functions."""
        self.categories = ["billing", "technical", "delivery", "general"]
        self.statuses = ["pending", "in_progress", "resolved", "closed"]
        # ETA calculation: hours from now based on category
        self.category_eta_hours = {
            "billing": 4,      # Billing issues typically resolved in 4 hours
            "technical": 8,    # Technical issues may take longer, 8 hours
            "delivery": 2,     # Delivery issues are urgent, 2 hours
            "general": 6       # General support, 6 hours
        }

    def calculate_eta(self, category: str) -> datetime:
        """
        Calculate expected resolution datetime based on category.
        
        Args:
            category: Ticket category
            
        Returns:
            Expected resolution datetime
        """
        hours = self.category_eta_hours.get(category.lower(), 6)
        return datetime.utcnow() + timedelta(hours=hours)

    def detect_intent(self, message: str, tickets: List[Dict]) -> Dict[str, any]:
        """
        Detect user intent from message.
        
        Args:
            message: User's message
            tickets: List of user's tickets
            
        Returns:
            Dictionary with intent type and parameters
        """
        message_lower = message.lower()
        
        # Detect reopen intent
        reopen_keywords = ["reopen", "open again", "not resolved", "still have issue", 
                          "not fixed", "still broken", "issue persists", "reopen ticket"]
        if any(keyword in message_lower for keyword in reopen_keywords):
            # Try to extract ticket ID
            ticket_id = self._extract_ticket_id(message, tickets)
            if ticket_id:
                return {
                    "intent": "reopen_ticket",
                    "ticket_id": ticket_id,
                    "confidence": 0.9
                }
        
        # Detect create ticket intent
        create_keywords = ["create ticket", "new ticket", "open ticket", "submit ticket", 
                          "file a ticket", "report issue", "i need help", "i have a problem",
                          "create a ticket", "make a ticket", "raise a ticket"]
        if any(keyword in message_lower for keyword in create_keywords):
            # Extract ticket message (everything after create keywords or the full message)
            ticket_message = message
            for keyword in create_keywords:
                if keyword in message_lower:
                    idx = message_lower.find(keyword)
                    ticket_message = message[idx + len(keyword):].strip()
                    # Remove common connectors
                    ticket_message = re.sub(r'^(for|about|regarding|concerning|with)\s+', '', ticket_message, flags=re.IGNORECASE).strip()
                    break
            
            # If message is too short after extraction, use full message
            if len(ticket_message) < 10:
                ticket_message = message
            
            return {
                "intent": "create_ticket",
                "ticket_message": ticket_message,
                "confidence": 0.9
            }
        
        # Detect category/team change intent
        change_keywords = ["change category", "change team", "wrong category", 
                         "should be", "this is actually", "reassign", "move to"]
        category_keywords = {
            "billing": ["billing", "payment", "invoice", "charge", "refund", "billing team"],
            "technical": ["technical", "tech", "bug", "error", "software", "technical team"],
            "delivery": ["delivery", "shipping", "order", "package", "delivery team"],
            "general": ["general", "other", "general team"]
        }
        
        if any(keyword in message_lower for keyword in change_keywords):
            # Detect which category they want
            for category, keywords in category_keywords.items():
                if any(kw in message_lower for kw in keywords):
                    ticket_id = self._extract_ticket_id(message, tickets)
                    if ticket_id:
                        return {
                            "intent": "update_category",
                            "ticket_id": ticket_id,
                            "category": category,
                            "confidence": 0.85
                        }
        
        return {
            "intent": "chat",
            "confidence": 1.0
        }

    def _extract_ticket_id(self, message: str, tickets: List[Dict]) -> Optional[int]:
        """
        Extract ticket ID from message or return most recent ticket.
        
        Args:
            message: User message
            tickets: List of tickets
            
        Returns:
            Ticket ID or None
        """
        # Try to find ticket ID in message (e.g., "ticket #123" or "ticket 123")
        patterns = [
            r'ticket\s*#?\s*(\d+)',
            r'#(\d+)',
            r'ticket\s+(\d+)',
            r'(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                ticket_id = int(match.group(1))
                # Verify ticket exists in user's tickets
                if any(t.get('id') == ticket_id for t in tickets):
                    return ticket_id
        
        # If no specific ticket mentioned, return most recent ticket
        if tickets:
            return tickets[0].get('id')
        
        return None

    def update_ticket_category(
        self,
        ticket_id: int,
        new_category: str,
        user_id: int,
        db: Session
    ) -> Dict[str, any]:
        """
        Update ticket category and assigned team.
        
        Args:
            ticket_id: Ticket ID to update
            new_category: New category name
            user_id: User ID (for authorization)
            db: Database session
            
        Returns:
            Dictionary with success status and updated ticket info
        """
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.user_id == user_id
        ).first()
        
        if not ticket:
            return {
                "success": False,
                "error": "Ticket not found or you don't have permission to update it"
            }
        
        # Validate category
        if new_category.lower() not in self.categories:
            return {
                "success": False,
                "error": f"Invalid category. Must be one of: {', '.join(self.categories)}"
            }
        
        old_category = ticket.category
        old_team = ticket.assigned_team
        old_status = ticket.status
        old_eta = ticket.expected_resolved_datetime
        
        # Update category, team, status, and recalculate ETA
        ticket.category = new_category.lower()
        ticket.assigned_team = elsai_service.get_assigned_team(new_category.lower())
        ticket.status = "pending"  # Reset status to pending when category changes
        ticket.expected_resolved_datetime = self.calculate_eta(new_category.lower())  # Recalculate ETA
        
        db.commit()
        db.refresh(ticket)
        
        return {
            "success": True,
            "ticket_id": ticket.id,
            "old_category": old_category,
            "new_category": ticket.category,
            "old_team": old_team,
            "new_team": ticket.assigned_team,
            "old_status": old_status,
            "new_status": ticket.status,
            "old_eta": old_eta.isoformat() if old_eta else None,
            "new_eta": ticket.expected_resolved_datetime.isoformat() if ticket.expected_resolved_datetime else None,
            "message": f"Ticket #{ticket.id} category updated from {old_category} to {ticket.category}. Team reassigned to {ticket.assigned_team}. Status reset to pending. ETA recalculated."
        }

    def reopen_ticket(
        self,
        ticket_id: int,
        user_id: int,
        db: Session
    ) -> Dict[str, any]:
        """
        Reopen a closed or resolved ticket.
        
        Args:
            ticket_id: Ticket ID to reopen
            user_id: User ID (for authorization)
            db: Database session
            
        Returns:
            Dictionary with success status and updated ticket info
        """
        ticket = db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.user_id == user_id
        ).first()
        
        if not ticket:
            return {
                "success": False,
                "error": "Ticket not found or you don't have permission to update it"
            }
        
        if ticket.status not in ["resolved", "closed"]:
            return {
                "success": False,
                "error": f"Ticket is currently {ticket.status}. Only resolved or closed tickets can be reopened."
            }
        
        old_status = ticket.status
        ticket.status = "pending"
        
        db.commit()
        db.refresh(ticket)
        
        return {
            "success": True,
            "ticket_id": ticket.id,
            "old_status": old_status,
            "new_status": ticket.status,
            "message": f"Ticket #{ticket.id} has been reopened and is now pending review."
        }

    def create_ticket(
        self,
        ticket_message: str,
        customer_name: str,
        user_id: int,
        db: Session
    ) -> Dict[str, any]:
        """
        Create a new ticket with automatic classification.
        
        Args:
            ticket_message: Ticket message/content
            customer_name: Customer name
            user_id: User ID
            db: Database session
            
        Returns:
            Dictionary with success status and created ticket info
        """
        from services.elsai_service import ElsAIService
        
        elsai = ElsAIService()
        
        # Classify ticket using ElsAI NLI
        classification = elsai.classify_ticket(ticket_message)
        category = classification["label"]
        assigned_team = elsai.get_assigned_team(category)
        
        # Calculate ETA based on category
        expected_resolved_datetime = self.calculate_eta(category)
        
        # Create ticket in database
        ticket = Ticket(
            customer=customer_name,
            message=ticket_message,
            category=category,
            assigned_team=assigned_team,
            status="pending",
            confidence=classification.get("confidence"),
            user_id=user_id,
            expected_resolved_datetime=expected_resolved_datetime
        )
        
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Generate voice mail and send email notification
        try:
            eta_str = ticket.expected_resolved_datetime.strftime("%Y-%m-%d %H:%M:%S") if ticket.expected_resolved_datetime else None
            audio_file_path = tts_service.generate_ticket_created_voicemail(
                ticket_id=ticket.id,
                customer_name=customer_name,
                category=ticket.category,
                assigned_team=ticket.assigned_team,
                eta=eta_str
            )
            
            # Send email with voice mail attachment
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.email:
                email_service.send_ticket_created_email(
                    to_email=user.email,
                    ticket_id=ticket.id,
                    ticket_message=ticket_message,
                    category=ticket.category,
                    assigned_team=ticket.assigned_team,
                    customer_name=customer_name,
                    eta=eta_str,
                    audio_file_path=audio_file_path
                )
        except Exception as e:
            print(f"⚠️  Failed to generate/send voice mail for ticket #{ticket.id}: {e}")
            import traceback
            traceback.print_exc()
        
        return {
            "success": True,
            "ticket_id": ticket.id,
            "category": ticket.category,
            "assigned_team": ticket.assigned_team,
            "status": ticket.status,
            "eta": ticket.expected_resolved_datetime.isoformat() if ticket.expected_resolved_datetime else None,
            "message": f"Ticket #{ticket.id} created successfully! Category: {ticket.category}, Assigned to: {ticket.assigned_team}, Status: {ticket.status}."
        }

