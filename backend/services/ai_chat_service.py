"""AI Chat Agent service for conversational ticket queries."""
import os
import json
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
    openai_client_available = True
except ImportError:
    openai_client_available = False
    OpenAI = None


class AIChatService:
    """Service for AI-powered chat agent that answers questions about tickets."""

    def __init__(self):
        """Initialize AI chat service."""
        self.model_name = os.getenv("ELSAI_MODEL", "gpt-5-nano")
        self.openai_client = None
        
        if openai_client_available:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)

    def format_ticket_context(self, tickets: List[Dict]) -> str:
        """
        Format customer tickets into context for AI agent.
        
        Args:
            tickets: List of ticket dictionaries
            
        Returns:
            Formatted context string
        """
        if not tickets:
            return "No pending tickets found for this customer."
        
        context_parts = [
            f"Customer has {len(tickets)} pending ticket(s):\n"
        ]
        
        for idx, ticket in enumerate(tickets, 1):
            context_parts.append(
                f"Ticket #{ticket.get('id', idx)}:\n"
                f"  - Category: {ticket.get('category', 'N/A')}\n"
                f"  - Status: {ticket.get('status', 'N/A')}\n"
                f"  - Assigned Team: {ticket.get('assignedTeam', 'N/A')}\n"
                f"  - Message: {ticket.get('message', 'N/A')[:200]}...\n"
                f"  - Created: {ticket.get('createdAt', 'N/A')}\n"
                f"  - Estimated Time to Resolve: {ticket.get('expectedResolvedDatetime', 'N/A')}\n"
            )
        
        return "\n".join(context_parts)

    def detect_action_intent(
        self,
        user_query: str,
        ticket_context: str
    ) -> Dict[str, any]:
        """
        Detect if user wants to perform an action (update category, reopen ticket).
        
        Args:
            user_query: User's message
            ticket_context: Formatted ticket context
            
        Returns:
            Dictionary with detected intent and parameters
        """
        if not self.openai_client:
            return {"intent": "chat", "confidence": 1.0}
        
        try:
            detection_prompt = f"""Analyze this customer message and determine if they want to:
1. Create a new ticket
2. Change ticket category/team assignment
3. Reopen a ticket
4. Just chat/ask questions

Customer message: "{user_query}"

Available tickets:
{ticket_context}

Respond ONLY with a JSON object in this exact format:
{{
    "intent": "create_ticket" | "update_category" | "reopen_ticket" | "chat",
    "ticket_id": <number or null>,
    "category": "<billing|technical|delivery|general>" or null,
    "ticket_message": "<extracted ticket message>" or null,
    "confidence": <0.0 to 1.0>
}}

If intent is "create_ticket", extract the ticket message/content from the user's query and include it in "ticket_message".
If intent is "chat", only include intent and confidence. Do not include any other text."""

            models_using_responses_api = ["gpt-5-nano"]
            use_responses_api = any(model in self.model_name.lower() for model in models_using_responses_api)
            
            if use_responses_api:
                response = self.openai_client.responses.create(
                    model=self.model_name,
                    input=detection_prompt,
                    store=True
                )
                response_text = response.output_text
            else:
                response = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": detection_prompt}],
                    temperature=0.3,
                    max_tokens=200
                )
                response_text = response.choices[0].message.content
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group())
                return intent_data
            
            return {"intent": "chat", "confidence": 1.0}
            
        except Exception as e:
            print(f"Intent detection error: {str(e)}")
            return {"intent": "chat", "confidence": 1.0}

    def generate_chat_response(
        self,
        user_query: str,
        ticket_context: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        action_result: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate AI chat response based on user query and ticket context.
        
        Args:
            user_query: User's question or message
            ticket_context: Formatted context about customer's tickets
            conversation_history: Previous conversation messages
            action_result: Result message from executed action (if any)
            
        Returns:
            Dictionary with response text and status
        """
        if not self.openai_client:
            return {
                "response": "AI chat service is not available. Please check API configuration.",
                "error": "OpenAI client not initialized"
            }
        
        try:
            # Build system prompt with ticket context
            action_context = f"\n\nAction Result: {action_result}\n" if action_result else ""
            system_prompt = (
                "You are a helpful AI assistant for a ticket support system. "
                "You help customers understand their tickets and answer questions about them. "
                "You can also help them update ticket categories or reopen tickets. "
                "Be friendly, concise, and helpful. "
                f"\n\nCustomer's Ticket Information:\n{ticket_context}{action_context}\n\n"
                "Answer the customer's questions based on their ticket information. "
                "If an action was just performed, acknowledge it naturally in your response. "
                "If they ask about something not in their tickets, politely let them know."
            )
            
            # Build messages array
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-10:]:  # Limit to last 10 messages
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current user query
            messages.append({"role": "user", "content": user_query})
            
            # Check if using responses API (gpt-5-nano) or chat completions
            models_using_responses_api = ["gpt-5-nano"]
            use_responses_api = any(model in self.model_name.lower() for model in models_using_responses_api)
            
            if use_responses_api:
                # Use responses API
                combined_prompt = "\n".join([
                    msg["content"] for msg in messages
                ])
                
                response = self.openai_client.responses.create(
                    model=self.model_name,
                    input=combined_prompt,
                    store=True
                )
                
                return {
                    "response": response.output_text,
                    "status": "success"
                }
            else:
                # Use chat completions API
                response = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
                
                return {
                    "response": response.choices[0].message.content,
                    "status": "success"
                }
                
        except Exception as e:
            error_msg = str(e)
            return {
                "response": f"I apologize, but I encountered an error: {error_msg}. Please try again later.",
                "error": error_msg,
                "status": "error"
            }

