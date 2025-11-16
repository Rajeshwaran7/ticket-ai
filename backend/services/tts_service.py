"""Text-to-Speech service using gTTS (Google Text-to-Speech) for voice mail generation."""
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

try:
    from gtts import gTTS
    import io
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("⚠️  gTTS not installed. Install with: pip install gtts")
    print("   Voice mail functionality will be disabled.")


class TTSService:
    """Service for converting text to speech using gTTS (Google Text-to-Speech)."""
    
    def __init__(self, output_dir: str = "uploads/voicemail"):
        """
        Initialize TTS service.
        
        Args:
            output_dir: Directory to save generated audio files
        """
        self.output_dir = output_dir
        self.enabled = False
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        if TTS_AVAILABLE:
            self.enabled = True
            print("✅ gTTS (Google Text-to-Speech) initialized successfully")
        else:
            self.enabled = False
    
    def generate_voicemail(
        self,
        text: str,
        filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate voice mail audio file from text.
        
        Args:
            text: Text to convert to speech
            filename: Optional custom filename (without extension)
            
        Returns:
            Path to generated audio file (relative to project root) or None if failed
        """
        if not self.enabled:
            print("⚠️  TTS service not available. Cannot generate voice mail.")
            return None
        
        try:
            # Generate unique filename if not provided
            if not filename:
                filename = f"voicemail_{uuid.uuid4().hex[:8]}"
            
            # Ensure filename doesn't have extension
            filename = Path(filename).stem
            
            # Output file path (gTTS generates MP3 files)
            output_path = os.path.join(self.output_dir, f"{filename}.mp3")
            
            # Generate speech using gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            
            # Verify file was created
            if os.path.exists(output_path):
                # Return relative path
                relative_path = output_path.replace("\\", "/")
                print(f"✅ Voice mail generated: {relative_path}")
                return relative_path
            else:
                print(f"❌ Voice mail file was not created: {output_path}")
                return None
                
        except Exception as e:
            print(f"❌ Error generating voice mail: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_ticket_created_voicemail(
        self,
        ticket_id: int,
        customer_name: str,
        category: str,
        assigned_team: str,
        eta: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate voice mail for ticket creation.
        
        Args:
            ticket_id: Ticket ID
            customer_name: Customer name
            category: Ticket category
            assigned_team: Assigned team
            eta: Expected resolution time (optional)
            
        Returns:
            Path to generated audio file or None if failed
        """
        text = f"""
        Hello {customer_name}, 
        
        Your ticket number {ticket_id} has been created successfully.
        Category: {category.replace('_', ' ').title()}
        Assigned Team: {assigned_team}
        Status: Pending
        """
        
        if eta:
            text += f"Expected resolution time: {eta}"
        
        text += """
        
        Our team will review your ticket and get back to you soon.
        Thank you for contacting us.
        """
        
        filename = f"ticket_{ticket_id}_created"
        return self.generate_voicemail(text.strip(), filename)
    
    def generate_ticket_status_voicemail(
        self,
        ticket_id: int,
        customer_name: str,
        old_status: str,
        new_status: str,
        ticket_message: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate voice mail for ticket status update.
        
        Args:
            ticket_id: Ticket ID
            customer_name: Customer name
            old_status: Previous status
            new_status: New status
            ticket_message: Ticket message (optional)
            
        Returns:
            Path to generated audio file or None if failed
        """
        status_messages = {
            "in_progress": "Your ticket is now being worked on by our team.",
            "resolved": "Your ticket has been resolved!",
            "closed": "Your ticket has been closed."
        }
        
        status_message = status_messages.get(
            new_status,
            f"Your ticket status has been updated to {new_status.replace('_', ' ')}."
        )
        
        text = f"""
        Hello {customer_name},
        
        This is an update regarding your ticket number {ticket_id}.
        
        {status_message}
        
        Previous Status: {old_status.replace('_', ' ').title()}
        Current Status: {new_status.replace('_', ' ').title()}
        """
        
        if ticket_message:
            # Truncate message if too long
            short_message = ticket_message[:100] + "..." if len(ticket_message) > 100 else ticket_message
            text += f"\n\nTicket Message: {short_message}"
        
        text += """
        
        Thank you for your patience.
        """
        
        filename = f"ticket_{ticket_id}_status_{new_status}"
        return self.generate_voicemail(text.strip(), filename)

