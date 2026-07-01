import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from library.models import Notification, CustomUser, ActivityLog

logger = logging.getLogger(__name__)

def send_notification(user, title, message, notification_type):
    """
    Creates an in-app notification and optionally logs an activity.
    """
    try:
        # Create in-app notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        # Log system activity
        ActivityLog.objects.create(
            user=user,
            action=f"Notification: {notification_type}",
            details=f"Title: {title} | Message: {message[:100]}"
        )
        return notification
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None


def send_email_notification(subject, recipient_email, message_body, context=None):
    """
    Sends an email using Django's email configuration.
    Falls back to console if settings.DEBUG is true or connection fails.
    """
    if not recipient_email:
        return False
        
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'library@system.local')
        
        # Send simple plain text email
        send_mail(
            subject=subject,
            message=message_body,
            from_email=from_email,
            recipient_list=[recipient_email],
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {e}")
        # Log email fail to ActivityLog for tracking
        user = CustomUser.objects.filter(email=recipient_email).first()
        ActivityLog.objects.create(
            user=user,
            action="Email Failed",
            details=f"To: {recipient_email} | Subject: {subject} | Error: {str(e)[:150]}"
        )
        return False
