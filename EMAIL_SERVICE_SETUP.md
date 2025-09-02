# Email Service Setup Guide

The RFPO application now includes a comprehensive email service for sending templated emails to users. This guide explains how to configure and use the email service.

## Features

- ✅ SMTP configuration with Gmail support
- ✅ Jinja2 templated HTML emails
- ✅ Welcome emails for new users
- ✅ Approval notification emails
- ✅ Project assignment notification emails
- ✅ Automatic email sending on user creation
- ✅ Fallback handling for email failures

## Environment Variables

Add these environment variables to your `.env` file:

```bash
# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Optional
APP_URL=http://localhost:5000
SUPPORT_EMAIL=support@yourcompany.com
```

### Gmail Setup

For Gmail, you'll need to:

1. Enable 2-Factor Authentication on your Google account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → App passwords
   - Generate a password for "Mail"
   - Use this app password as `MAIL_PASSWORD`

## Testing the Email Service

Run the test script to verify your configuration:

```bash
python test_email_service.py
```

This will:
- Check your email configuration
- Test SMTP connection
- Verify template rendering
- Optionally send a test email

## Email Templates

Templates are stored in `templates/email/`:

- `welcome.html` - Welcome email for new users
- `approval_notification.html` - RFPO approval notifications
- `user_added_to_project.html` - Project assignment notifications

### Template Variables

#### Welcome Email
- `user_name` - User's display name
- `user_email` - User's email address
- `temp_password` - Temporary password (optional)
- `login_url` - Application login URL
- `support_email` - Support contact email

#### Approval Notification
- `user_name` - Approver's name
- `rfpo_id` - RFPO identifier
- `approval_type` - Type of approval required
- `rfpo_url` - Direct link to RFPO

#### Project Assignment
- `user_name` - User's name
- `project_name` - Project name
- `role` - User's role in project
- `projects_url` - Projects page URL

## Usage

### Automatic Email Sending

Welcome emails are automatically sent when users are created through the admin panel. No additional code required.

### Manual Email Sending

```python
from email_service import send_welcome_email, send_approval_notification

# Send welcome email
success = send_welcome_email(
    user_email="user@example.com",
    user_name="John Doe",
    temp_password="TempPass123"
)

# Send approval notification
success = send_approval_notification(
    user_email="approver@example.com",
    user_name="Jane Smith",
    rfpo_id="RFPO-2025-001",
    approval_type="Technical Review"
)
```

### Custom Email Sending

```python
from email_service import EmailService

email_service = EmailService()

# Send templated email
success = email_service.send_templated_email(
    to_emails=["user@example.com"],
    template_name="welcome",
    template_data={
        'user_name': 'John Doe',
        'user_email': 'john@example.com'
    },
    subject="Welcome to RFPO!"
)

# Send custom HTML email
success = email_service.send_email(
    to_emails=["user@example.com"],
    subject="Custom Email",
    body_html="<h1>Hello World!</h1>",
    body_text="Hello World!"
)
```

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify Gmail app password is correct
   - Ensure 2FA is enabled on your Google account
   - Check that MAIL_USERNAME matches your Gmail address

2. **Connection Timeout**
   - Verify MAIL_SERVER and MAIL_PORT settings
   - Check firewall/network restrictions
   - Try different SMTP servers if needed

3. **Template Not Found**
   - Ensure templates exist in `templates/email/`
   - Check file permissions
   - Verify template names match exactly

4. **Email Not Received**
   - Check spam/junk folders
   - Verify recipient email addresses
   - Check email service logs

### Debug Mode

Enable debug logging by setting environment variable:

```bash
LOG_LEVEL=DEBUG
```

### Test Connection

```python
from email_service import test_email_connection

if test_email_connection():
    print("Email service is working!")
else:
    print("Email service needs configuration")
```

## Security Notes

- Never commit email passwords to version control
- Use environment variables for sensitive configuration
- Consider using app-specific passwords instead of account passwords
- Regularly rotate email credentials
- Monitor email sending for abuse

## Future Enhancements

Potential improvements for the email service:

- Email queue for bulk sending
- Email templates editor in admin panel
- Email delivery status tracking
- Bounce and unsubscribe handling
- Rich text editor for email composition
- Email analytics and reporting
