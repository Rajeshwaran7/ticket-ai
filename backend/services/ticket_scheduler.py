"""Scheduler service for automatic ticket status updates."""
import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from dotenv import load_dotenv

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    print("⚠️  APScheduler not installed. Install with: pip install apscheduler")
    print("   Cron job functionality will be disabled.")

from models.ticket import Ticket, SessionLocal
from models.user import User
from services.email_service import EmailService

load_dotenv()

email_service = EmailService()


def update_ticket_statuses():
    """
    Cron job function to automatically update ticket statuses.
    - After 1 minute: pending -> in_progress
    - After 3 minutes: in_progress -> resolved
    """
    db = SessionLocal()
    
    try:
        now = datetime.utcnow()
        
        # Update pending tickets to in_progress after 1 minute
        one_minute_ago = now - timedelta(minutes=1)
        pending_tickets = db.query(Ticket).filter(
            Ticket.status == "pending",
            Ticket.created_at <= one_minute_ago
        ).all()
        
        for ticket in pending_tickets:
            old_status = ticket.status
            ticket.status = "in_progress"
            db.commit()
            db.refresh(ticket)
            
            # Send email notification
            if ticket.user_id:
                user = db.query(User).filter(User.id == ticket.user_id).first()
                if user and user.email:
                    email_service.send_ticket_status_email(
                        to_email=user.email,
                        ticket_id=ticket.id,
                        ticket_message=ticket.message,
                        old_status=old_status,
                        new_status="in_progress",
                        customer_name=ticket.customer
                    )
            
            print(f"Updated ticket #{ticket.id} from {old_status} to in_progress")
        
        # Update in_progress tickets to resolved after 3 minutes from creation
        three_minutes_ago = now - timedelta(minutes=3)
        in_progress_tickets = db.query(Ticket).filter(
            Ticket.status == "in_progress",
            Ticket.created_at <= three_minutes_ago
        ).all()
        
        for ticket in in_progress_tickets:
            old_status = ticket.status
            ticket.status = "resolved"
            db.commit()
            db.refresh(ticket)
            
            # Send email notification
            if ticket.user_id:
                user = db.query(User).filter(User.id == ticket.user_id).first()
                if user and user.email:
                    email_service.send_ticket_status_email(
                        to_email=user.email,
                        ticket_id=ticket.id,
                        ticket_message=ticket.message,
                        old_status=old_status,
                        new_status="resolved",
                        customer_name=ticket.customer
                    )
            
            print(f"Updated ticket #{ticket.id} from {old_status} to resolved")
        
    except Exception as e:
        print(f"Error in ticket status update cron job: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler for ticket status updates.
    Runs every 30 seconds to check for tickets that need status updates.
    
    Returns:
        BackgroundScheduler instance or None if APScheduler not available
    """
    if not APSCHEDULER_AVAILABLE:
        print("⚠️  Cannot start scheduler: APScheduler not installed")
        print("   Install with: pip install apscheduler")
        return None
    
    scheduler = BackgroundScheduler()
    
    # Run every 30 seconds to check for tickets needing updates
    scheduler.add_job(
        update_ticket_statuses,
        trigger=IntervalTrigger(seconds=90),
        id='update_ticket_statuses',
        name='Update ticket statuses automatically',
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ Ticket status scheduler started (checking every 30 seconds)")
    
    return scheduler

