"""Embedding service for generating vector embeddings from text."""
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Install with: pip install sentence-transformers")
    print("   Embedding functionality will be disabled.")

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self):
        """Initialize embedding service."""
        self.model = None
        self.use_openai = False
        self.enabled = False
        
        # Check for OpenAI API key
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if OPENAI_AVAILABLE and openai_api_key:
            try:
                openai.api_key = openai_api_key
                self.use_openai = True
                self.enabled = True
                print("✅ OpenAI embeddings initialized")
            except Exception as e:
                print(f"⚠️  Failed to initialize OpenAI embeddings: {e}")
        
        # Fallback to sentence-transformers
        if not self.enabled and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Use a lightweight, fast model
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
                self.enabled = True
                print("✅ SentenceTransformer embeddings initialized (all-MiniLM-L6-v2)")
            except Exception as e:
                print(f"⚠️  Failed to initialize SentenceTransformer: {e}")
                self.enabled = False
        
        if not self.enabled:
            print("⚠️  No embedding service available. Install sentence-transformers or set OPENAI_API_KEY")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            if self.use_openai and OPENAI_AVAILABLE:
                # Use OpenAI embeddings
                response = openai.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            elif self.model:
                # Use sentence-transformers
                embedding = self.model.encode(text, convert_to_numpy=True)
                return embedding.tolist()
            else:
                return None
        except Exception as e:
            print(f"❌ Error generating embedding: {e}")
            return None
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts (batch processing).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not self.enabled:
            return [None] * len(texts)
        
        try:
            if self.use_openai and OPENAI_AVAILABLE:
                # OpenAI batch embeddings
                response = openai.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                return [item.embedding for item in response.data]
            elif self.model:
                # Sentence-transformers batch embeddings
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                return [emb.tolist() for emb in embeddings]
            else:
                return [None] * len(texts)
        except Exception as e:
            print(f"❌ Error generating batch embeddings: {e}")
            return [None] * len(texts)

