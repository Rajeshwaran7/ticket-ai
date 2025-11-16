"""Email service for sending ticket notifications."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.audio import MIMEAudio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class EmailService:
    """Service for sending email notifications."""

    def __init__(self):
        """Initialize email service with SMTP configuration."""
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)
        self.enabled = bool(self.smtp_user and self.smtp_pass)

    def send_ticket_status_email(
        self,
        to_email: str,
        ticket_id: int,
        ticket_message: str,
        old_status: str,
        new_status: str,
        customer_name: str,
        audio_file_path: Optional[str] = None
    ) -> bool:
        """
        Send email notification when ticket status changes.
        
        Args:
            to_email: Recipient email address
            ticket_id: Ticket ID
            ticket_message: Ticket message content
            old_status: Previous ticket status
            new_status: New ticket status
            customer_name: Customer name
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"Email service not configured. Would send to {to_email}: Ticket #{ticket_id} status changed to {new_status}")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Ticket #{ticket_id} Status Update: {new_status.title()}"
            msg['From'] = self.smtp_from
            msg['To'] = to_email

            # Email body
            status_messages = {
                "in_progress": "Your ticket is now being worked on by our team.",
                "resolved": "Your ticket has been resolved!",
                "closed": "Your ticket has been closed."
            }

            status_message = status_messages.get(new_status, f"Your ticket status has been updated to {new_status}.")

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px; }}
                    .ticket-info {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                    .status-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; }}
                    .status-in_progress {{ background: #3498db; color: white; }}
                    .status-resolved {{ background: #27ae60; color: white; }}
                    .status-closed {{ background: #95a5a6; color: white; }}
                    .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎫 Ticket Status Update</h1>
                    </div>
                    <div class="content">
                        <p>Hello {customer_name},</p>
                        <p>{status_message}</p>
                        
                        <div class="ticket-info">
                            <p><strong>Ticket ID:</strong> #{ticket_id}</p>
                            <p><strong>Previous Status:</strong> {old_status.title()}</p>
                            <p><strong>Current Status:</strong> 
                                <span class="status-badge status-{new_status}">{new_status.replace('_', ' ').title()}</span>
                            </p>
                            <p><strong>Message:</strong> {ticket_message[:200]}{'...' if len(ticket_message) > 200 else ''}</p>
                        </div>
                        
                        <p>You can view your ticket details by logging into your account.</p>
                        
                        <div class="footer">
                            <p>This is an automated notification. Please do not reply to this email.</p>
                            <p>&copy; 2024 Ticket AI System. All rights reserved.</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            text_body = f"""
            Ticket Status Update
            
            Hello {customer_name},
            
            {status_message}
            
            Ticket ID: #{ticket_id}
            Previous Status: {old_status.title()}
            Current Status: {new_status.replace('_', ' ').title()}
            Message: {ticket_message[:200]}{'...' if len(ticket_message) > 200 else ''}
            
            You can view your ticket details by logging into your account.
            
            This is an automated notification. Please do not reply to this email.
            """

            # Attach parts
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach audio file if provided
            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    # Determine audio subtype based on file extension
                    audio_subtype = 'mpeg' if audio_file_path.lower().endswith('.mp3') else 'wav'
                    audio_ext = 'mp3' if audio_file_path.lower().endswith('.mp3') else 'wav'
                    
                    with open(audio_file_path, 'rb') as audio_file:
                        audio_data = audio_file.read()
                        audio_attachment = MIMEAudio(audio_data, _subtype=audio_subtype)
                        audio_attachment.add_header(
                            'Content-Disposition',
                            'attachment',
                            filename=f'ticket_{ticket_id}_voicemail.{audio_ext}'
                        )
                        msg.attach(audio_attachment)
                        print(f"✅ Audio attachment added: {audio_file_path}")
                except Exception as e:
                    print(f"⚠️  Failed to attach audio file: {e}")

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            print(f"Email sent successfully to {to_email} for ticket #{ticket_id}")
            return True

        except Exception as e:
            print(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_ticket_created_email(
        self,
        to_email: str,
        ticket_id: int,
        ticket_message: str,
        category: str,
        assigned_team: str,
        customer_name: str,
        eta: Optional[str] = None,
        audio_file_path: Optional[str] = None
    ) -> bool:
        """
        Send email notification when ticket is created.
        
        Args:
            to_email: Recipient email address
            ticket_id: Ticket ID
            ticket_message: Ticket message content
            category: Ticket category
            assigned_team: Assigned team
            customer_name: Customer name
            eta: Expected resolution time (optional)
            audio_file_path: Path to voice mail audio file (optional)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"Email service not configured. Would send to {to_email}: Ticket #{ticket_id} created")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Ticket #{ticket_id} Created Successfully"
            msg['From'] = self.smtp_from
            msg['To'] = to_email

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f8f9fa; padding: 20px; border-radius: 0 0 10px 10px; }}
                    .ticket-info {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                    .status-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; background: #3498db; color: white; }}
                    .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎫 Ticket Created</h1>
                    </div>
                    <div class="content">
                        <p>Hello {customer_name},</p>
                        <p>Your ticket has been created successfully!</p>
                        
                        <div class="ticket-info">
                            <p><strong>Ticket ID:</strong> #{ticket_id}</p>
                            <p><strong>Category:</strong> {category.replace('_', ' ').title()}</p>
                            <p><strong>Assigned Team:</strong> {assigned_team}</p>
                            <p><strong>Status:</strong> <span class="status-badge">Pending</span></p>
                            {f'<p><strong>Expected Resolution:</strong> {eta}</p>' if eta else ''}
                            <p><strong>Message:</strong> {ticket_message[:200]}{'...' if len(ticket_message) > 200 else ''}</p>
                        </div>
                        
                        <p>Our team will review your ticket and get back to you soon.</p>
                        
                        {f'<p><strong>📧 Voice Mail:</strong> Please check the attached audio file for a voice message.</p>' if audio_file_path else ''}
                        
                        <div class="footer">
                            <p>This is an automated notification. Please do not reply to this email.</p>
                            <p>&copy; 2024 Ticket AI System. All rights reserved.</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            text_body = f"""
            Ticket Created
            
            Hello {customer_name},
            
            Your ticket has been created successfully!
            
            Ticket ID: #{ticket_id}
            Category: {category.replace('_', ' ').title()}
            Assigned Team: {assigned_team}
            Status: Pending
            {f'Expected Resolution: {eta}' if eta else ''}
            Message: {ticket_message[:200]}{'...' if len(ticket_message) > 200 else ''}
            
            Our team will review your ticket and get back to you soon.
            {f'Please check the attached audio file for a voice message.' if audio_file_path else ''}
            
            This is an automated notification. Please do not reply to this email.
            """

            # Attach parts
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach audio file if provided
            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    # Determine audio subtype based on file extension
                    audio_subtype = 'mpeg' if audio_file_path.lower().endswith('.mp3') else 'wav'
                    audio_ext = 'mp3' if audio_file_path.lower().endswith('.mp3') else 'wav'
                    
                    with open(audio_file_path, 'rb') as audio_file:
                        audio_data = audio_file.read()
                        audio_attachment = MIMEAudio(audio_data, _subtype=audio_subtype)
                        audio_attachment.add_header(
                            'Content-Disposition',
                            'attachment',
                            filename=f'ticket_{ticket_id}_created_voicemail.{audio_ext}'
                        )
                        msg.attach(audio_attachment)
                        print(f"✅ Audio attachment added: {audio_file_path}")
                except Exception as e:
                    print(f"⚠️  Failed to attach audio file: {e}")

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            print(f"Email sent successfully to {to_email} for ticket #{ticket_id}")
            return True

        except Exception as e:
            print(f"Failed to send email to {to_email}: {str(e)}")
            return False

