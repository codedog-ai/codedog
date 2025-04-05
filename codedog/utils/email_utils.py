import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from os import environ as env


class EmailNotifier:
    """Email notification utility for sending code review reports."""
    
    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        smtp_username: str = None,
        smtp_password: str = None,
        use_tls: bool = True,
    ):
        """Initialize EmailNotifier with SMTP settings.
        
        Args:
            smtp_server: SMTP server address (defaults to env var SMTP_SERVER)
            smtp_port: SMTP server port (defaults to env var SMTP_PORT)
            smtp_username: SMTP username (defaults to env var SMTP_USERNAME)
            smtp_password: SMTP password (defaults to env var SMTP_PASSWORD)
            use_tls: Whether to use TLS for SMTP connection (defaults to True)
        """
        self.smtp_server = smtp_server or env.get("SMTP_SERVER")
        self.smtp_port = int(smtp_port or env.get("SMTP_PORT", 587))
        self.smtp_username = smtp_username or env.get("SMTP_USERNAME")
        
        # 优先从系统环境变量获取密码，如果不存在再从 .env 文件获取
        self.smtp_password = smtp_password or os.environ.get("CODEDOG_SMTP_PASSWORD") or env.get("SMTP_PASSWORD")
        self.use_tls = use_tls
        
        # Validate required settings
        if not all([self.smtp_server, self.smtp_username, self.smtp_password]):
            missing = []
            if not self.smtp_server:
                missing.append("SMTP_SERVER")
            if not self.smtp_username:
                missing.append("SMTP_USERNAME")
            if not self.smtp_password:
                missing.append("SMTP_PASSWORD or CODEDOG_SMTP_PASSWORD (environment variable)")
            
            raise ValueError(f"Missing required email configuration: {', '.join(missing)}")
    
    def send_report(
        self,
        to_emails: List[str],
        subject: str,
        markdown_content: str,
        from_email: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
    ) -> bool:
        """Send code review report as email.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            markdown_content: Report content in markdown format
            from_email: Sender email (defaults to SMTP_USERNAME)
            cc_emails: List of CC email addresses
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not to_emails:
            raise ValueError("No recipient emails provided")
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email or self.smtp_username
        msg["To"] = ", ".join(to_emails)
        
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
            all_recipients = to_emails + cc_emails
        else:
            all_recipients = to_emails
        
        # Attach markdown content as both plain text and HTML
        text_part = MIMEText(markdown_content, "plain")
        
        # Basic markdown to HTML conversion
        # A more sophisticated conversion could be done with a library like markdown2
        html_content = f"<pre>{markdown_content}</pre>"
        html_part = MIMEText(html_content, "html")
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        try:
            # Create a secure SSL context
            context = ssl.create_default_context() if self.use_tls else None
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls(context=context)
                
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(
                    self.smtp_username, all_recipients, msg.as_string()
                )
            
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False


def send_report_email(
    to_emails: List[str],
    subject: str,
    markdown_content: str,
    cc_emails: Optional[List[str]] = None,
) -> bool:
    """Helper function to send code review report via email.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        markdown_content: Report content in markdown format
        cc_emails: List of CC email addresses
            
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Check if email notification is enabled
    if not env.get("EMAIL_ENABLED", "").lower() in ("true", "1", "yes"):
        print("Email notifications are disabled. Set EMAIL_ENABLED=true to enable.")
        return False
    
    try:
        notifier = EmailNotifier()
        return notifier.send_report(
            to_emails=to_emails,
            subject=subject,
            markdown_content=markdown_content,
            cc_emails=cc_emails,
        )
    except ValueError as e:
        print(f"Email configuration error: {str(e)}")
        return False
    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication Error: Invalid username or password.")
        print("If using Gmail, make sure to:")
        print("1. Enable 2-step verification for your Google account")
        print("2. Generate an App Password at https://myaccount.google.com/apppasswords")
        print("3. Use that App Password in your .env file, not your regular Gmail password")
        return False
    except Exception as e:
        print(f"Unexpected error sending email: {str(e)}")
        return False 