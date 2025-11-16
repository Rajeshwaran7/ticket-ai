"""Chat session and message models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from models.ticket import Base


class ChatSession(Base):
    """Chat session model for storing conversation sessions."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)  # Auto-generated from first message
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to messages
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    def to_dict(self) -> dict:
        """Convert chat session to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }


class ChatMessage(Base):
    """Chat message model for storing individual messages."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    audio_file_path = Column(String(500), nullable=True)  # Path to audio file for voice messages
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to session
    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self) -> dict:
        """Convert chat message to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "audio_file_path": self.audio_file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

