"""ElsAI Foundry NLI API integration service using elsai-nli package."""
import os
import time
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

from elsai_nli.natural_language_interface import CSVAgentHandler
from services.elsai_connection import ElsaiConnection



class ElsAIService:
    """Service for interacting with ElsAI Foundry NLI using Python package."""

    def __init__(self):
        """Initialize ElsAI service with model configuration from environment."""
        self.model_name = os.getenv("ELSAI_MODEL", "gpt-4o-mini")
        self.agent_type = os.getenv("ELSAI_AGENT_TYPE", "openai-functions")
        self.csv_path = Path(__file__).parent.parent / "data" / "ticket_routing.csv"
        self.agent = None
        self.elsai_connection = ElsaiConnection()
        self.labels = ["billing", "technical", "delivery", "general"]
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the CSV agent handler using ElsaiConnection."""
        if not self.csv_path.exists():
            print(f"Error: CSV file not found at {self.csv_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"CSV path resolved to: {self.csv_path.absolute()}")
            return

        # Check if ElsaiConnection is available
        if not self.elsai_connection.is_available():
            print("Error: Elsai Azure OpenAI Connector not available. Check environment variables.")
            return

        try:
            # Get the connector instance
            connector = self.elsai_connection.get_connector()
            
            print(f"Initializing ElsAI agent with CSV: {self.csv_path}")
            print(f"Model: {self.model_name}, Agent Type: {self.agent_type}")
            print("Using Elsai Azure OpenAI Connector")
            
            # CSVAgentHandler expects a LangChain-compatible model
            # We'll use the connector's invoke method directly for classification
            # For now, we'll use a wrapper approach
            self.agent = connector
            print("ElsAI agent initialized successfully with ElsaiConnection")
        except Exception as e:
            print(f"Error: Failed to initialize ElsAI agent: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.agent = None

    def classify_ticket(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify ticket text using ElsAI Azure OpenAI Connector.

        Args:
            text: The ticket message text to classify

        Returns:
            Dictionary with label and confidence, or error information
        """
        if not self.elsai_connection.is_available():
            error_msg = "ElsAI Azure OpenAI Connector not initialized."
            if not self.csv_path.exists():
                error_msg += f" CSV file not found at {self.csv_path}"
            else:
                error_msg += " Check environment variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME"
            return {
                "label": "general",
                "confidence": "0.85",
                "error": error_msg
            }

        # Retry mechanism with exponential backoff for 429 errors
        max_retries = 3
        base_delay = 1  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                question = (
                    f"Based on the ticket routing rules in the CSV, classify this ticket message "
                    f"into one of these categories: billing, technical, delivery, or general. "
                    f"Ticket message: '{text}'. "
                    f"Respond with only the category name (billing, technical, delivery, or general)."
                )

                # Use ElsaiConnection invoke method
                messages = [{"role": "user", "content": question}]
                response = self.elsai_connection.invoke(messages=messages)

                # Extract category from response
                category = self._extract_category(response)
                confidence = self._calculate_confidence(text, category)

                return {
                    "label": category,
                    "confidence": str(confidence)
                }
            except Exception as e:
                error_str = str(e)
                error_type = type(e).__name__
                
                # Check for rate limit errors (429)
                is_rate_limit = (
                    "429" in error_str or
                    "rate limit" in error_str.lower() or
                    "too many requests" in error_str.lower() or
                    error_type in ["RateLimitError"]
                )
                
                # Check for quota/billing errors (should not retry)
                is_quota_error = (
                    "quota" in error_str.lower() or
                    "insufficient_quota" in error_str.lower() or
                    "billing" in error_str.lower()
                )
                
                # If it's a rate limit and we have retries left, wait and retry
                if is_rate_limit and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    print(f"Rate limit error (429) detected. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                
                # If quota error or final retry failed, use fallback
                if is_rate_limit or is_quota_error:
                    print(f"Azure OpenAI API rate limit/quota error detected after {attempt + 1} attempts, using fallback classification")
                    return self._fallback_classify(text)
                
                # For other errors, log and use fallback immediately
                print(f"Classification error ({error_type}): {error_str}")
                return self._fallback_classify(text)
        
        # If we exhausted all retries, use fallback
        print(f"Exhausted all retry attempts, using fallback classification")
        return self._fallback_classify(text)


    def _extract_category(self, response: str) -> str:
        """
        Extract category from agent response.

        Args:
            response: Agent response text

        Returns:
            Category name (billing, technical, delivery, or general)
        """
        response_lower = response.lower()

        for label in self.labels:
            if label.lower() in response_lower:
                return label

        return "general"

    def _calculate_confidence(self, text: str, category: str) -> float:
        """
        Calculate confidence score based on keyword matching.

        Args:
            text: Ticket text
            category: Classified category

        Returns:
            Confidence score between 0.0 and 1.0
        """
        text_lower = text.lower()

        keyword_mapping = {
            "billing": ["payment", "invoice", "charge", "refund", "billing", "account", "subscription", "fee"],
            "technical": ["error", "bug", "issue", "problem", "technical", "software", "hardware", "login", "access"],
            "delivery": ["shipping", "delivery", "order", "tracking", "package", "shipment", "arrive"],
            "general": ["question", "inquiry", "help", "information"]
        }

        keywords = keyword_mapping.get(category, [])
        matches = sum(1 for keyword in keywords if keyword in text_lower)

        if matches > 0:
            return min(0.95, 0.7 + (matches * 0.05))
        return 0.75

    def _fallback_classify(self, text: str) -> Dict[str, Optional[str]]:
        """
        Fallback classification using keyword matching when API is unavailable.
        
        Args:
            text: Ticket text to classify
            
        Returns:
            Dictionary with label and confidence
        """
        text_lower = text.lower()
        
        keyword_mapping = {
            "billing": ["payment", "invoice", "charge", "refund", "billing", "account", "subscription", "fee", "bill", "paid", "money"],
            "technical": ["error", "bug", "issue", "problem", "technical", "software", "hardware", "login", "access", "crash", "broken", "not working"],
            "delivery": ["shipping", "delivery", "order", "tracking", "package", "shipment", "arrive", "shipped", "dispatch", "transit"],
            "general": ["question", "inquiry", "help", "information", "support"]
        }
        
        scores = {}
        for category, keywords in keyword_mapping.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                scores[category] = matches
        
        if scores:
            # Get category with highest score
            category = max(scores, key=scores.get)
            confidence = min(0.95, 0.7 + (scores[category] * 0.05))
        else:
            category = "general"
            confidence = 0.75
        
        return {
            "label": category,
            "confidence": str(confidence),
            "warning": "Using fallback keyword-based classification (Azure OpenAI API unavailable)"
        }

    def get_assigned_team(self, category: str) -> str:
        """
        Map category to assigned team.

        Args:
            category: The ticket category from NLI

        Returns:
            Assigned team name
        """
        team_mapping = {
            "billing": "BillingTeam",
            "delivery": "DeliveryTeam",
            "technical": "TechSupport",
            "general": "GeneralSupport"
        }
        return team_mapping.get(category.lower(), "GeneralSupport")

