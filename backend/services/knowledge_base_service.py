"""Knowledge Base service for RAG (Retrieval Augmented Generation) using vector embeddings."""
import os
import json
import pickle
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from services.embedding_service import EmbeddingService
from services.document_service import DocumentService

try:
    import faiss
    import numpy as np
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️  faiss-cpu not installed. Install with: pip install faiss-cpu")
    print("   Knowledge base functionality will be limited.")


class KnowledgeBaseService:
    """Service for managing a knowledge base using vector embeddings and FAISS."""
    
    def __init__(self, kb_dir: str = "data/knowledge_base"):
        """
        Initialize knowledge base service.
        
        Args:
            kb_dir: Directory to store knowledge base data
        """
        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.kb_dir / "faiss_index.idx"
        self.metadata_file = self.kb_dir / "metadata.json"
        
        self.embedding_service = EmbeddingService()
        self.document_service = DocumentService()
        
        self.index = None
        self.metadata = []
        self.dimension = 384  # Default dimension for sentence-transformers
        
        # Initialize FAISS index
        self._initialize_index()
    
    def _initialize_index(self) -> None:
        """Initialize or load FAISS index."""
        if not FAISS_AVAILABLE:
            print("⚠️  FAISS not available. Knowledge base search will be disabled.")
            return
        
        try:
            # Load existing index if available
            if self.index_file.exists() and self.metadata_file.exists():
                self.index = faiss.read_index(str(self.index_file))
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                
                # Get dimension from existing index
                if self.index.ntotal > 0:
                    self.dimension = self.index.d
                
                print(f"✅ Loaded knowledge base with {len(self.metadata)} documents")
            else:
                # Create new index - dimension will be set when first embedding is generated
                print("📚 Creating new knowledge base")
                self.metadata = []
        except Exception as e:
            print(f"⚠️  Error loading knowledge base: {e}")
            self.index = None
            self.metadata = []
    
    def _get_embedding_dimension(self) -> int:
        """
        Get embedding dimension by generating a test embedding.
        
        Returns:
            Embedding dimension
        """
        test_embedding = self.embedding_service.generate_embedding("test")
        if test_embedding:
            return len(test_embedding)
        return 384  # Default for sentence-transformers
    
    def add_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        session_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a document to the knowledge base.
        
        Args:
            file_content: Document file content
            filename: Original filename
            content_type: MIME type of the file
            session_id: Optional session ID
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary with success status and document info
        """
        if not self.embedding_service.enabled:
            return {
                "success": False,
                "error": "Embedding service not available"
            }
        
        if not FAISS_AVAILABLE:
            return {
                "success": False,
                "error": "FAISS not available. Install faiss-cpu package."
            }
        
        try:
            # Process document to extract text
            doc_result = self.document_service.process_document(
                file_content=file_content,
                filename=filename,
                content_type=content_type,
                session_id=session_id
            )
            
            if not doc_result.get("extracted_text"):
                return {
                    "success": False,
                    "error": "Could not extract text from document"
                }
            
            extracted_text = doc_result["extracted_text"]
            
            # Generate embedding
            embedding = self.embedding_service.generate_embedding(extracted_text)
            if not embedding:
                return {
                    "success": False,
                    "error": "Failed to generate embedding"
                }
            
            # Update dimension if needed
            if self.dimension != len(embedding):
                self.dimension = len(embedding)
                # Recreate index if dimension changed
                if self.index is not None and self.index.ntotal > 0:
                    print(f"⚠️  Embedding dimension changed. Recreating index...")
                    self._recreate_index()
            
            # Initialize index if needed
            if self.index is None:
                self.index = faiss.IndexFlatL2(self.dimension)
            
            # Convert embedding to numpy array
            embedding_array = np.array([embedding], dtype=np.float32)
            
            # Add to FAISS index
            self.index.add(embedding_array)
            
            # Store metadata (store full text for RAG context)
            doc_metadata = {
                "id": len(self.metadata),
                "filename": filename,
                "content_type": content_type,
                "text": extracted_text,  # Store full text for context retrieval
                "file_path": doc_result.get("file_path"),
                "session_id": session_id,
                "metadata": metadata or {}
            }
            self.metadata.append(doc_metadata)
            
            # Save index and metadata
            self._save_index()
            
            return {
                "success": True,
                "document_id": doc_metadata["id"],
                "filename": filename,
                "text_preview": extracted_text[:200]
            }
            
        except Exception as e:
            print(f"❌ Error adding document to knowledge base: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _recreate_index(self) -> None:
        """Recreate FAISS index with new dimension."""
        if not FAISS_AVAILABLE or not self.metadata:
            return
        
        try:
            # Re-embed all existing documents
            print("🔄 Re-embedding all documents...")
            embeddings = []
            for doc in self.metadata:
                text = doc.get("text", "")
                embedding = self.embedding_service.generate_embedding(text)
                if embedding:
                    embeddings.append(embedding)
                else:
                    # Use zero vector if embedding fails
                    embeddings.append([0.0] * self.dimension)
            
            if embeddings:
                # Create new index
                self.index = faiss.IndexFlatL2(self.dimension)
                embedding_array = np.array(embeddings, dtype=np.float32)
                self.index.add(embedding_array)
                print(f"✅ Recreated index with {len(embeddings)} documents")
        except Exception as e:
            print(f"❌ Error recreating index: {e}")
            self.index = None
    
    def get_context_for_query(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.5
    ) -> Optional[str]:
        """
        Search knowledge base for relevant documents and return context.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold (0.0 to 1.0)
            
        Returns:
            Combined context string from relevant documents, or None if no matches
        """
        if not self.embedding_service.enabled:
            return None
        
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return None
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            if not query_embedding:
                return None
            
            # Convert to numpy array
            query_array = np.array([query_embedding], dtype=np.float32)
            
            # Search in FAISS index
            k = min(top_k, self.index.ntotal)
            distances, indices = self.index.search(query_array, k)
            
            # Collect relevant documents
            relevant_docs = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.metadata):
                    # Convert L2 distance to similarity (lower distance = higher similarity)
                    # Using inverse distance normalized
                    similarity = 1.0 / (1.0 + distance)
                    
                    if similarity >= min_similarity:
                        doc = self.metadata[idx]
                        relevant_docs.append({
                            "text": doc.get("text", ""),
                            "filename": doc.get("filename", "unknown"),
                            "similarity": similarity
                        })
            
            if not relevant_docs:
                return None
            
            # Combine relevant documents into context
            context_parts = []
            for doc in relevant_docs:
                context_parts.append(
                    f"[Document: {doc['filename']}]\n{doc['text']}\n"
                )
            
            return "\n".join(context_parts)
            
        except Exception as e:
            print(f"❌ Error searching knowledge base: {e}")
            return None
    
    def _save_index(self) -> None:
        """Save FAISS index and metadata to disk."""
        if not FAISS_AVAILABLE or self.index is None:
            return
        
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_file))
            
            # Save metadata
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Error saving knowledge base: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_documents": len(self.metadata),
            "index_size": self.index.ntotal if self.index is not None else 0,
            "dimension": self.dimension,
            "faiss_available": FAISS_AVAILABLE,
            "embedding_enabled": self.embedding_service.enabled
        }

