import os
import sys
import socket
import smtplib
import ssl
from getpass import getpass
from dotenv import load_dotenv
from codedog.utils.email_utils import EmailNotifier

def check_smtp_connection(smtp_server, smtp_port):
    """Test basic connection to SMTP server."""
    print(f"\nTesting connection to {smtp_server}:{smtp_port}...")
    try:
        # Try opening a socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout
        result = sock.connect_ex((smtp_server, int(smtp_port)))
        sock.close()
        
        if result == 0:
            print("✅ Connection successful")
            return True
        else:
            print(f"❌ Connection failed (error code: {result})")
            return False
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def test_full_smtp_connection(smtp_server, smtp_port, use_tls=True):
    """Test full SMTP connection without login."""
    print("\nTesting SMTP protocol connection...")
    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10) as server:
            # Get the server's response code
            code, message = server.ehlo()
            if code >= 200 and code < 300:
                print(f"✅ EHLO successful: {code} {message.decode() if isinstance(message, bytes) else message}")
            else:
                print(f"⚠️ EHLO response: {code} {message.decode() if isinstance(message, bytes) else message}")
            
            if use_tls:
                print("Starting TLS...")
                context = ssl.create_default_context()
                server.starttls(context=context)
                # Get the server's response after TLS
                code, message = server.ehlo()
                if code >= 200 and code < 300:
                    print(f"✅ TLS EHLO successful: {code} {message.decode() if isinstance(message, bytes) else message}")
                else:
                    print(f"⚠️ TLS EHLO response: {code} {message.decode() if isinstance(message, bytes) else message}")
            
            return True
    except Exception as e:
        print(f"❌ SMTP protocol error: {str(e)}")
        return False

def test_email_connection():
    """Test the email connection and send a test email."""
    # Load environment variables
    load_dotenv()
    
    # Get email configuration
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("CODEDOG_SMTP_PASSWORD")
    notification_emails = os.environ.get("NOTIFICATION_EMAILS")
    
    # Print configuration (without password)
    print(f"SMTP Server: {smtp_server}")
    print(f"SMTP Port: {smtp_port}")
    print(f"SMTP Username: {smtp_username}")
    print(f"Password configured: {'Yes' if smtp_password else 'No'}")
    print(f"Notification emails: {notification_emails}")
    
    if not notification_emails:
        print("ERROR: No notification emails configured. Please set NOTIFICATION_EMAILS in .env")
        return False
    
    # Test basic connection
    if not check_smtp_connection(smtp_server, int(smtp_port)):
        print("\nSMTP connection failed. Please check:")
        print("- Your internet connection")
        print("- Firewall settings")
        print("- That the SMTP server and port are correct")
        return False
    
    # Test SMTP protocol
    if not test_full_smtp_connection(smtp_server, smtp_port):
        print("\nSMTP protocol handshake failed. Please check:")
        print("- Your network isn't blocking SMTP traffic")
        print("- The server supports the protocols we're using")
        return False
    
    # Ask for password if not configured
    if not smtp_password:
        print("\nNo SMTP password found in configuration.")
        if smtp_server == "smtp.gmail.com":
            print("For Gmail, you need to use an App Password:")
            print("1. Go to https://myaccount.google.com/apppasswords")
            print("2. Create an App Password for 'Mail'")
        smtp_password = getpass("Please enter SMTP password: ")
    
    # Send test email
    try:
        print("\nAttempting to create EmailNotifier...")
        notifier = EmailNotifier(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password
        )
        
        print("EmailNotifier created successfully.")
        
        to_emails = [email.strip() for email in notification_emails.split(",") if email.strip()]
        
        print(f"\nSending test email to: {', '.join(to_emails)}")
        success = notifier.send_report(
            to_emails=to_emails,
            subject="[CodeDog] Email Configuration Test",
            markdown_content="# CodeDog Email Test\n\nIf you're receiving this email, your CodeDog email configuration is working correctly.",
        )
        
        if success:
            print("✅ Test email sent successfully!")
            return True
        else:
            print("❌ Failed to send test email.")
            return False
            
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication Error: {str(e)}")
        if smtp_server == "smtp.gmail.com":
            print("\nGmail authentication failed. Please make sure:")
            print("1. 2-Step Verification is enabled for your Google account")
            print("2. You're using an App Password, not your regular Gmail password")
            print("3. The App Password was generated for the 'Mail' application")
            print("\nYou can generate an App Password at: https://myaccount.google.com/apppasswords")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("CodeDog Email Configuration Test")
    print("================================\n")
    result = test_email_connection()
    sys.exit(0 if result else 1) 