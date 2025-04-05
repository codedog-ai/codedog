# Email Notification Setup Guide

CodeDog can send code review and evaluation reports via email. This guide will help you set up email notifications correctly, with specific instructions for Gmail users.

## Configuration Steps

1. Open your `.env` file and configure the following settings:

```
# Email notification settings
EMAIL_ENABLED="true"
NOTIFICATION_EMAILS="your.email@example.com"  # Can be comma-separated for multiple recipients

# SMTP server settings
SMTP_SERVER="smtp.gmail.com"  # Use your email provider's SMTP server
SMTP_PORT="587"              # Common port for TLS connections
SMTP_USERNAME="your.email@gmail.com"  # The email that will send notifications
SMTP_PASSWORD="your_app_password"    # See Gmail-specific instructions below
```

## Gmail Specific Setup

Gmail requires special setup due to security measures:

1. **Enable 2-Step Verification**:
   - Go to your [Google Account Security Settings](https://myaccount.google.com/security)
   - Enable "2-Step Verification" if not already enabled

2. **Create an App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" as the app and your device
   - Click "Generate"
   - Copy the 16-character password generated
   - Use this app password in your `.env` file as `SMTP_PASSWORD`

3. **Important Notes**:
   - Do NOT use your regular Gmail password - it will not work
   - App passwords only work when 2-Step Verification is enabled
   - For security, consider using a dedicated Google account for sending notifications

## Testing Your Configuration

You can test your email configuration using the provided test script:

```bash
python test_email.py
```

This script will attempt to:
1. Read your email configuration from the `.env` file
2. Connect to the SMTP server
3. Send a test email to the addresses in `NOTIFICATION_EMAILS`

If you see "Test email sent successfully!", your configuration is working.

## Troubleshooting

**Authentication Errors**
- Check that you've used an App Password, not your regular Gmail password
- Verify that 2-Step Verification is enabled on your Google Account
- Ensure you're using the correct SMTP server and port

**Connection Errors**
- Check your internet connection
- Some networks may block outgoing SMTP connections
- Try using a different network or contact your network administrator

**Other Issues**
- Make sure `EMAIL_ENABLED` is set to "true" in your `.env` file
- Verify that `NOTIFICATION_EMAILS` contains at least one valid email address
- Check that your Gmail account doesn't have additional security restrictions

## Environment Variables

For enhanced security, you can set the SMTP password as an environment variable instead of storing it in the `.env` file:

```bash
# Linux/macOS
export CODEDOG_SMTP_PASSWORD="your_app_password"

# Windows (CMD)
set CODEDOG_SMTP_PASSWORD="your_app_password"

# Windows (PowerShell)
$env:CODEDOG_SMTP_PASSWORD="your_app_password"
```

The program will check for `CODEDOG_SMTP_PASSWORD` environment variable before using the value in the `.env` file. 