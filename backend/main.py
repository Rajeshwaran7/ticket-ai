"""Main FastAPI application."""
from dotenv import load_dotenv
import os
import atexit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import tickets, auth
from models.ticket import init_db, SessionLocal
from models import chat  # Import to register chat models
from services.ticket_scheduler import start_scheduler

# Load environment variables
load_dotenv()

# Initialize database
init_db()

# Global scheduler variable
scheduler = None

# Register shutdown handler
def shutdown_scheduler():
    """Shutdown scheduler on app exit."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        print("✅ Ticket status scheduler stopped")

atexit.register(shutdown_scheduler)

# Create FastAPI app
app = FastAPI(
    title="AI Powered Ticket Routing System",
    description="Ticket routing system using ElsAI Foundry NLI with authentication",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory for serving uploaded files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router)
app.include_router(tickets.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Powered Ticket Routing System API",
        "version": "1.0.0"
    }


@app.on_event("startup")
async def startup_event():
    """Start scheduler on application startup."""
    global scheduler
    try:
        scheduler = start_scheduler()
        if scheduler:
            print("✅ Background scheduler initialized successfully")
    except Exception as e:
        print(f"⚠️  Failed to start scheduler: {str(e)}")
        scheduler = None


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on application shutdown."""
    shutdown_scheduler()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

