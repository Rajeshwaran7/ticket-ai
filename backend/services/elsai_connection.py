"""Reusable Elsai Connection service using Azure OpenAI Connector."""
import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

load_dotenv()

try:
    from elsai_model.azure_openai import AzureOpenAIConnector
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False
    AzureOpenAIConnector = None


class ElsaiConnection:
    """
    Singleton-like reusable connection class for Elsai Azure OpenAI Connector.
    
    This class provides a centralized way to manage Azure OpenAI connections
    and ensures connection reuse across the application.
    """
    
    _instance: Optional['ElsaiConnection'] = None
    _connector: Optional[AzureOpenAIConnector] = None
    
    def __new__(cls):
        """Create or return existing instance (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the connection if not already initialized."""
        if self._initialized:
            return
        
        self._initialized = True
        self._initialize_connector()
    
    def _initialize_connector(self) -> None:
        """
        Initialize Azure OpenAI Connector with configuration from environment variables.
        
        Required environment variables:
        - AZURE_OPENAI_API_KEY: API key for Azure OpenAI
        - AZURE_OPENAI_ENDPOINT: Endpoint URL of Azure OpenAI resource
        - OPENAI_API_VERSION: API version (e.g., 2023-05-15)
        - AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name
        - AZURE_OPENAI_TEMPERATURE: Temperature value (optional, default 0.1)
        """
        if not AZURE_OPENAI_AVAILABLE:
            print("⚠️  elsai-model package not available. Install with:")
            print("   pip install --index-url https://elsai-core-package.optisolbusiness.com/root/elsai-model/ elsai-model==1.2.1")
            return
        
        try:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("OPENAI_API_VERSION", "2023-05-15")
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            temperature = float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.1"))
            
            if not azure_endpoint:
                print("⚠️  AZURE_OPENAI_ENDPOINT not set in environment variables")
                return
            
            if not azure_api_key:
                print("⚠️  AZURE_OPENAI_API_KEY not set in environment variables")
                return
            
            if not deployment_name:
                print("⚠️  AZURE_OPENAI_DEPLOYMENT_NAME not set in environment variables")
                return
            
            self._connector = AzureOpenAIConnector(
                azure_endpoint=azure_endpoint,
                openai_api_key=azure_api_key,
                openai_api_version=api_version,
                deployment_name=deployment_name,
                temperature=temperature
            )
            
            print("✅ Elsai Azure OpenAI Connector initialized successfully")
            print(f"   Endpoint: {azure_endpoint}")
            print(f"   Deployment: {deployment_name}")
            print(f"   API Version: {api_version}")
            
        except Exception as e:
            print(f"❌ Failed to initialize Elsai Azure OpenAI Connector: {e}")
            import traceback
            traceback.print_exc()
            self._connector = None
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke the Azure OpenAI connector with messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Hello"}]
        
        Returns:
            Response text from the model
        
        Raises:
            RuntimeError: If connector is not initialized
        """
        if not self._connector:
            raise RuntimeError(
                "Elsai Azure OpenAI Connector not initialized. "
                "Check environment variables: AZURE_OPENAI_ENDPOINT, "
                "AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME"
            )
        
        try:
            response = self._connector.invoke(messages=messages)
            
            # Extract text content from ChatCompletion object
            # The response can be either a string or a ChatCompletion object
            if isinstance(response, str):
                return response
            elif hasattr(response, 'choices') and len(response.choices) > 0:
                # OpenAI ChatCompletion format
                return response.choices[0].message.content
            elif hasattr(response, 'content'):
                # Direct content attribute
                return response.content
            else:
                # Fallback: convert to string
                return str(response)
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error invoking Azure OpenAI connector: {error_msg}")
            raise
    
    def stream(self, messages: List[Dict[str, str]]):
        """
        Stream responses from Azure OpenAI connector.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
        
        Yields:
            Response chunks as strings
        
        Raises:
            RuntimeError: If connector is not initialized
        """
        if not self._connector:
            raise RuntimeError(
                "Elsai Azure OpenAI Connector not initialized. "
                "Check environment variables: AZURE_OPENAI_ENDPOINT, "
                "AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME"
            )
        
        try:
            for chunk in self._connector.stream(messages=messages):
                yield chunk
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error streaming from Azure OpenAI connector: {error_msg}")
            raise
    
    def is_available(self) -> bool:
        """
        Check if the connector is available and initialized.
        
        Returns:
            True if connector is initialized, False otherwise
        """
        return self._connector is not None
    
    def get_connector(self) -> Optional[AzureOpenAIConnector]:
        """
        Get the underlying Azure OpenAI connector instance.
        
        Returns:
            AzureOpenAIConnector instance or None if not initialized
        """
        return self._connector

