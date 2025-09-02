"""
Email Service Module
Handles email sending functionality with template support
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

def load_env_file(env_file='.env'):
    """Load environment variables from .env file"""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Set environment variable if not already set
                    if key not in os.environ:
                        os.environ[key] = value

# Load .env file automatically
load_env_file()

class EmailService:
    """Email service for sending templated emails"""
    
    def __init__(self, config=None):
        """Initialize email service with configuration"""
        self.config = config or {}
        
        # SMTP Configuration from environment variables
        self.smtp_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('MAIL_PORT', 587))
        self.use_tls = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
        self.username = os.environ.get('MAIL_USERNAME')
        self.password = os.environ.get('MAIL_PASSWORD')
        self.default_sender = os.environ.get('MAIL_DEFAULT_SENDER', self.username)
        
        # Template configuration
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates', 'email')
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate email configuration"""
        if not self.username or not self.password:
            logger.warning("Email credentials not configured. Email service will not function.")
            return False
        
        if not self.smtp_server:
            logger.warning("SMTP server not configured. Email service will not function.")
            return False
            
        return True
    
    def _create_smtp_connection(self):
        """Create and configure SMTP connection"""
        try:
            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            # Enable TLS if configured
            if self.use_tls:
                server.starttls()
            
            # Login with credentials
            if self.username and self.password:
                server.login(self.username, self.password)
            
            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {str(e)}")
            raise
    
    def send_email(self, 
                   to_emails: List[str], 
                   subject: str, 
                   body_text: str = None,
                   body_html: str = None,
                   from_email: str = None,
                   cc_emails: List[str] = None,
                   bcc_emails: List[str] = None,
                   attachments: List[Dict[str, Any]] = None) -> bool:
        """
        Send email with optional HTML content and attachments
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject line
            body_text: Plain text body (optional)
            body_html: HTML body (optional)
            from_email: Sender email (defaults to configured sender)
            cc_emails: List of CC recipients (optional)
            bcc_emails: List of BCC recipients (optional)
            attachments: List of attachment dicts with 'filename' and 'content' keys
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Validate inputs
            if not to_emails:
                logger.error("No recipient emails provided")
                return False
            
            if not subject:
                logger.error("No email subject provided")
                return False
            
            if not body_text and not body_html:
                logger.error("No email body provided")
                return False
            
            # Use default sender if not provided
            sender_email = from_email or self.default_sender
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = sender_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            # Add CC and BCC if provided
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            if bcc_emails:
                msg['Bcc'] = ', '.join(bcc_emails)
            
            # Add plain text part
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Add HTML part
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    if 'filename' in attachment and 'content' in attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment['content'])
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {attachment["filename"]}'
                        )
                        msg.attach(part)
            
            # Get all recipients
            all_recipients = to_emails.copy()
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)
            
            # Send email
            server = self._create_smtp_connection()
            try:
                server.send_message(msg, to_addrs=all_recipients)
            finally:
                server.quit()
            
            logger.info(f"Email sent successfully to {len(all_recipients)} recipients: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def send_templated_email(self,
                           to_emails: List[str],
                           template_name: str,
                           template_data: Dict[str, Any] = None,
                           subject: str = None,
                           from_email: str = None,
                           cc_emails: List[str] = None,
                           bcc_emails: List[str] = None) -> bool:
        """
        Send email using Jinja2 template
        
        Args:
            to_emails: List of recipient email addresses
            template_name: Name of template file (without .html extension)
            template_data: Dictionary of data to pass to template
            subject: Email subject (if not in template)
            from_email: Sender email (defaults to configured sender)
            cc_emails: List of CC recipients (optional)
            bcc_emails: List of BCC recipients (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Load template
            template = self.jinja_env.get_template(f"{template_name}.html")
            
            # Prepare template data
            data = template_data or {}
            data.update({
                'current_date': datetime.now().strftime('%Y-%m-%d'),
                'current_year': datetime.now().year
            })
            
            # Render template
            html_content = template.render(**data)
            
            # Extract subject from template if not provided
            if not subject:
                # Try to extract subject from template data or use default
                subject = data.get('subject', f'RFPO Application - {template_name.title()}')
            
            # Create plain text version (basic HTML stripping)
            import re
            text_content = re.sub('<[^<]+?>', '', html_content)
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            
            # Send email
            return self.send_email(
                to_emails=to_emails,
                subject=subject,
                body_text=text_content,
                body_html=html_content,
                from_email=from_email,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails
            )
            
        except Exception as e:
            logger.error(f"Failed to send templated email: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, user_name: str, temp_password: str = None) -> bool:
        """
        Send welcome email to new user
        
        Args:
            user_email: User's email address
            user_name: User's display name
            temp_password: Temporary password (optional)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            'user_name': user_name,
            'user_email': user_email,
            'temp_password': temp_password,
            'login_url': os.environ.get('APP_URL', 'http://localhost:5000') + '/login',
            'support_email': os.environ.get('SUPPORT_EMAIL', 'support@rfpo.com'),
            'subject': 'Welcome to RFPO Application - Your Account is Ready'
        }
        
        return self.send_templated_email(
            to_emails=[user_email],
            template_name='welcome',
            template_data=template_data,
            subject=template_data['subject']
        )
    
    def send_approval_notification(self, user_email: str, user_name: str, rfpo_id: str, approval_type: str) -> bool:
        """
        Send approval notification email
        
        Args:
            user_email: User's email address
            user_name: User's display name
            rfpo_id: RFPO ID requiring approval
            approval_type: Type of approval needed
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            'user_name': user_name,
            'rfpo_id': rfpo_id,
            'approval_type': approval_type,
            'rfpo_url': os.environ.get('APP_URL', 'http://localhost:5000') + f'/admin/rfpo/{rfpo_id}/edit',
            'subject': f'RFPO Approval Required - {rfpo_id}'
        }
        
        return self.send_templated_email(
            to_emails=[user_email],
            template_name='approval_notification',
            template_data=template_data,
            subject=template_data['subject']
        )
    
    def send_user_added_to_project_email(self, user_email: str, user_name: str, project_name: str, role: str) -> bool:
        """
        Send notification when user is added to a project
        
        Args:
            user_email: User's email address
            user_name: User's display name
            project_name: Name of the project
            role: User's role in the project
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        template_data = {
            'user_name': user_name,
            'project_name': project_name,
            'role': role,
            'projects_url': os.environ.get('APP_URL', 'http://localhost:5000') + '/admin/projects',
            'subject': f'Added to Project: {project_name}'
        }
        
        return self.send_templated_email(
            to_emails=[user_email],
            template_name='user_added_to_project',
            template_data=template_data,
            subject=template_data['subject']
        )
    
    def test_connection(self) -> bool:
        """
        Test email service connection
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            server = self._create_smtp_connection()
            try:
                # Test connection by getting server status
                status = server.noop()
                return status[0] == 250
            finally:
                server.quit()
        except Exception as e:
            logger.error(f"Email connection test failed: {str(e)}")
            return False

# Global email service instance
email_service = EmailService()

# Convenience functions
def send_welcome_email(user_email: str, user_name: str, temp_password: str = None) -> bool:
    """Send welcome email to new user"""
    return email_service.send_welcome_email(user_email, user_name, temp_password)

def send_approval_notification(user_email: str, user_name: str, rfpo_id: str, approval_type: str) -> bool:
    """Send approval notification email"""
    return email_service.send_approval_notification(user_email, user_name, rfpo_id, approval_type)

def send_user_added_to_project_email(user_email: str, user_name: str, project_name: str, role: str) -> bool:
    """Send notification when user is added to a project"""
    return email_service.send_user_added_to_project_email(user_email, user_name, project_name, role)

def test_email_connection() -> bool:
    """Test email service connection"""
    return email_service.test_connection()
