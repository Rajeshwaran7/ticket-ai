"""Main FastAPI application."""
from dotenv import load_dotenv
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import tickets, auth
from models.ticket import init_db

# Load environment variables
load_dotenv()

# Initialize database
init_db()

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

