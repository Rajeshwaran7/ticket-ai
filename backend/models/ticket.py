"""Ticket model definition."""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


class Ticket(Base):
    """Ticket database model."""
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String(200), nullable=False, index=True)
    message = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    assigned_team = Column(String(100), nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(String(10), nullable=True)  # Store confidence score from NLI
    screenshot_path = Column(String(500), nullable=True)  # Path to uploaded screenshot
    user_id = Column(Integer, nullable=True, index=True)  # Foreign key to users table

    def to_dict(self) -> dict:
        """Convert ticket to dictionary."""
        return {
            "id": self.id,
            "customer": self.customer,
            "message": self.message,
            "category": self.category,
            "assignedTeam": self.assigned_team,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "confidence": self.confidence,
            "screenshot_path": self.screenshot_path,
            "user_id": self.user_id,
        }


# Database setup
def get_database_url() -> str:
    """
    Get database URL from environment variables.
    
    Returns:
        Database connection URL
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "root")
    db_name = os.getenv("DB_NAME", "ticket_ai")
    
    return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


DATABASE_URL = get_database_url()
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=False           # Set to True for SQL query logging
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

