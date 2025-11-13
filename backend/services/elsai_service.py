"""ElsAI Foundry NLI API integration service using elsai-nli package."""
import os
import time
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

from elsai_nli.natural_language_interface import CSVAgentHandler

# Try to import ChatOpenAI from langchain
try:
    from langchain_community.chat_models import ChatOpenAI
except ImportError:
    try:
        from langchain.chat_models import ChatOpenAI
    except ImportError:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            ChatOpenAI = None

# Import OpenAI for direct API calls (for gpt-5-nano)
try:
    from openai import OpenAI
    openai_client_available = True
except ImportError:
    openai_client_available = False
    OpenAI = None



class ElsAIService:
    """Service for interacting with ElsAI Foundry NLI using Python package."""

    def __init__(self):
        """Initialize ElsAI service with model configuration from environment."""
        self.model_name = os.getenv("ELSAI_MODEL", "gpt-5-nano")
        self.agent_type = os.getenv("ELSAI_AGENT_TYPE", "openai-functions")
        self.csv_path = Path(__file__).parent.parent / "data" / "ticket_routing.csv"
        self.agent = None
        self.model_instance = None
        self.supports_temperature = False
        self.use_direct_api = False  # Use direct OpenAI API for models that need it
        self.openai_client = None
        self.labels = ["billing", "technical", "delivery", "general"]
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the CSV agent handler."""
        if not self.csv_path.exists():
            print(f"Error: CSV file not found at {self.csv_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"CSV path resolved to: {self.csv_path.absolute()}")
            return

        # Check if model uses responses API (like gpt-5-nano)
        models_using_responses_api = ["gpt-5-nano"]
        self.use_direct_api = any(model in self.model_name.lower() for model in models_using_responses_api)

        if self.use_direct_api:
            # Use direct OpenAI API for models that use responses endpoint
            if not openai_client_available:
                print("Error: OpenAI client not available. Install openai package.")
                return
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("Error: OPENAI_API_KEY not set")
                return
            
            self.openai_client = OpenAI(api_key=api_key)
            print(f"Using direct OpenAI API for model: {self.model_name}")
            print(f"CSV file: {self.csv_path}")
            return

        # Use LangChain for standard chat/completions models
        if ChatOpenAI is None:
            print("Error: ChatOpenAI not available. Install langchain-openai or langchain.")
            return

        try:
            # Create model instance without temperature parameter
            self.model_instance = ChatOpenAI(model=self.model_name)
            self.supports_temperature = False
            
            print(f"Initializing ElsAI agent with CSV: {self.csv_path}")
            print(f"Model: {self.model_name}, Agent Type: {self.agent_type}")
            
            self.agent = CSVAgentHandler(
                csv_files=str(self.csv_path),
                model=self.model_instance,
                agent_type=self.agent_type,
                verbose=True
            )
            print("ElsAI agent initialized successfully")
        except Exception as e:
            error_str = str(e)
            # Temperature errors shouldn't happen since we don't set it, but handle gracefully
            if "temperature" in error_str.lower() and "unsupported" in error_str.lower():
                print(f"Temperature parameter error detected (LangChain internal), using fallback classification")
                self.agent = None  # Disable agent, will use fallback
            else:
                print(f"Error: Failed to initialize ElsAI agent: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                self.agent = None

    def classify_ticket(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify ticket text using ElsAI NLI Python package.

        Args:
            text: The ticket message text to classify

        Returns:
            Dictionary with label and confidence, or error information
        """
        # Use direct OpenAI API for models that support it (like gpt-5-nano)
        if self.use_direct_api and self.openai_client:
            return self._classify_with_direct_api(text)
        
        if self.agent is None:
            error_msg = "ElsAI agent not initialized."
            if not self.csv_path.exists():
                error_msg += f" CSV file not found at {self.csv_path}"
            elif ChatOpenAI is None and not self.use_direct_api:
                error_msg += " ChatOpenAI not available. Install langchain-community package."
            elif not os.getenv("OPENAI_API_KEY"):
                error_msg += " OPENAI_API_KEY not set. Please add it to your .env file."
            else:
                error_msg += " Check server logs for initialization errors."
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

                response = self.agent.ask_question(question)

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
                    print(f"OpenAI API rate limit/quota error detected after {attempt + 1} attempts, using fallback classification")
                    return self._fallback_classify(text)
                
                # Check for temperature errors - use fallback immediately
                # LangChain's agent executor sets temperature internally, so we can't prevent it
                if "temperature" in error_str.lower() and "unsupported" in error_str.lower():
                    print(f"Temperature parameter error detected (model doesn't support temperature customization), using fallback classification")
                    return self._fallback_classify(text)
                
                # For other errors, log and use fallback immediately
                print(f"Classification error ({error_type}): {error_str}")
                return self._fallback_classify(text)
        
        # If we exhausted all retries, use fallback
        print(f"Exhausted all retry attempts, using fallback classification")
        return self._fallback_classify(text)

    def _classify_with_direct_api(self, text: str) -> Dict[str, Optional[str]]:
        """
        Classify ticket using direct OpenAI responses API (for gpt-5-nano).
        
        Args:
            text: Ticket text to classify
            
        Returns:
            Dictionary with label and confidence
        """
        # Note: CSV context could be included in prompt for better classification
        # Currently using category list in prompt
        
        # Retry mechanism with exponential backoff
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                question = (
                    f"Based on these ticket routing categories: billing, technical, delivery, general. "
                    f"Classify this ticket message into one category: '{text}'. "
                    f"Respond with only the category name."
                )
                
                response = self.openai_client.responses.create(
                    model=self.model_name,
                    input=question,
                    store=True
                )
                print(f"Response: {response}")
                # Extract category from response
                category = self._extract_category(response.output_text)
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
                    "too many requests" in error_str.lower()
                )
                
                # If rate limit and we have retries left, wait and retry
                if is_rate_limit and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"Rate limit error (429) detected. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                
                # For other errors or final retry, use fallback
                print(f"Direct API error ({error_type}): {error_str}, using fallback")
                return self._fallback_classify(text)
        
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
            "warning": "Using fallback keyword-based classification (OpenAI API unavailable)"
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

