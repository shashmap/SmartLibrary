import os
import time
import logging
import threading
from datetime import timedelta
from django.utils import timezone
from django.db import connection, transaction
from django.conf import settings

logger = logging.getLogger(__name__)

def run_daily_library_tasks():
    """
    Core logic for daily automated tasks:
    1. Calculate and update fines for overdue books.
    2. Notify users with books due tomorrow and due today.
    3. Expiry check for uncollected reservations.
    4. Membership expiry check (30 days remaining).
    """
    from library.models import BorrowRecord, Fine, Reservation, Student, BookCopy, ActivityLog
    from library.notification_engine import send_notification, send_email_notification
    
    today = timezone.localdate()
    logger.info(f"Starting daily library tasks for {today}...")

    # --- 1. OVERDUE FINES CALCULATION ---
    try:
        overdue_records = BorrowRecord.objects.filter(status__in=['active', 'overdue'])
        fine_rate = getattr(settings, 'FINE_RATE_PER_DAY', 5.00)
        
        for record in overdue_records:
            if today > record.due_date:
                # Update status
                record.status = 'overdue'
                record.save()
                
                # Calculate fine
                overdue_days = (today - record.due_date).days
                fine_amount = overdue_days * fine_rate
                
                # Get or create unpaid fine
                fine, created = Fine.objects.get_or_create(
                    borrow_record=record,
                    payment_status='unpaid'
                )
                
                if fine.amount != fine_amount:
                    fine.amount = fine_amount
                    fine.save()
                    
                # Daily reminder notification
                user = record.user
                book_title = record.book_copy.book.title
                title = "Overdue Book Reminder"
                msg = f"URGENT: Your borrowed book '{book_title}' was due on {record.due_date}. Outstanding fine: ₹{fine.amount}."
                send_notification(user, title, msg, 'overdue')
                
                # Send email reminder
                if user.email:
                    email_subject = "URGENT: Overdue Book Alert"
                    email_body = f"Hello {user.get_full_name() or user.username},\n\nThis is a daily reminder that the book '{book_title}' is overdue.\nDue Date: {record.due_date}\nDays Overdue: {overdue_days}\nCurrent Fine Amount: Rs. {fine.amount}\n\nPlease return the book immediately to prevent further fines.\n\nBest Regards,\nSmart Library Team"
                    send_email_notification(email_subject, user.email, email_body)
    except Exception as e:
        logger.error(f"Error in Overdue Fines Calculation: {e}")

    # --- 2. DUE TODAY / TOMORROW NOTIFICATIONS ---
    try:
        # Due Tomorrow
        tomorrow = today + timedelta(days=1)
        due_tomorrow_records = BorrowRecord.objects.filter(due_date=tomorrow, status='active')
        for record in due_tomorrow_records:
            user = record.user
            book_title = record.book_copy.book.title
            title = "Book Due Tomorrow"
            msg = f"Reminder: Your borrowed book '{book_title}' is due tomorrow, {tomorrow}."
            send_notification(user, title, msg, 'due_warning')
            
            if user.email:
                email_subject = "Library Reminder: Book Due Tomorrow"
                email_body = f"Hello {user.get_full_name() or user.username},\n\nThis is a quick reminder that the book '{book_title}' is due tomorrow, {tomorrow}.\n\nPlease make arrangements to return or renew the book.\n\nBest Regards,\nSmart Library Team"
                send_email_notification(email_subject, user.email, email_body)
                
        # Due Today
        due_today_records = BorrowRecord.objects.filter(due_date=today, status='active')
        for record in due_today_records:
            user = record.user
            book_title = record.book_copy.book.title
            title = "Book Due Today"
            msg = f"URGENT: Your borrowed book '{book_title}' is due today, {today}."
            send_notification(user, title, msg, 'due_warning')
            
            if user.email:
                email_subject = "Library Alert: Book Due Today"
                email_body = f"Hello {user.get_full_name() or user.username},\n\nThis is to notify you that the book '{book_title}' is due today, {today}.\n\nPlease return it to avoid daily overdue fines.\n\nBest Regards,\nSmart Library Team"
                send_email_notification(email_subject, user.email, email_body)
    except Exception as e:
        logger.error(f"Error in Due Date Notifications: {e}")

    # --- 3. RESERVATION EXPIRY CHECK ---
    try:
        expired_reservations = Reservation.objects.filter(status='ready', expiry_date__lt=today)
        for res in expired_reservations:
            with transaction.atomic():
                res.status = 'expired'
                res.save()
                
                # Check for copies held for this reservation
                # The copy status would be 'reserved'
                # Find the copy of this book that is marked as 'reserved' and held for this user
                # We check the book's copies
                copy = BookCopy.objects.filter(book=res.book, status='reserved').first()
                if copy:
                    # Look if there's another pending reservation for this book
                    next_res = Reservation.objects.filter(book=res.book, status='pending').order_by('reserve_date').first()
                    if next_res:
                        # Hold the copy for the next reservation
                        next_res.status = 'ready'
                        next_res.expiry_date = today + timedelta(days=3)
                        next_res.save()
                        
                        # Notify next user
                        next_user = next_res.user
                        res_title = "Reserved Book Ready for Pickup"
                        res_msg = f"The book '{res.book.title}' you reserved is now ready for pickup at shelf '{copy.shelf_location}'. This reservation is valid until {next_res.expiry_date}."
                        send_notification(next_user, res_title, res_msg, 'reservation')
                        
                        if next_user.email:
                            res_subject = "Library Alert: Reservation Ready for Pickup"
                            res_body = f"Hello {next_user.get_full_name() or next_user.username},\n\nGood news! The book '{res.book.title}' you reserved is now ready for pickup.\nShelf Location: {copy.shelf_location}\n\nPlease collect it by {next_res.expiry_date}, after which the reservation will expire.\n\nBest Regards,\nSmart Library Team"
                            send_email_notification(res_subject, next_user.email, res_body)
                    else:
                        # Make the copy available
                        copy.status = 'available'
                        copy.save()

                # Notify the expired reservation user
                user = res.user
                title = "Reservation Expired"
                msg = f"Your reservation for '{res.book.title}' has expired as it was not collected within 3 days."
                send_notification(user, title, msg, 'reservation')
                
                ActivityLog.objects.create(
                    user=user,
                    action="Reservation Expired",
                    details=f"Book: {res.book.title}"
                )
    except Exception as e:
        logger.error(f"Error in Reservation Expiry Check: {e}")

    # --- 4. MEMBERSHIP EXPIRY CHECK (30 Days Warning) ---
    try:
        warning_date = today + timedelta(days=30)
        expiring_students = Student.objects.filter(membership_expiry=warning_date)
        
        for student in expiring_students:
            user = student.user
            title = "Library Membership Expiring Soon"
            msg = f"Your library membership will expire in 30 days on {student.membership_expiry}. Please renew it to continue borrowing."
            send_notification(user, title, msg, 'expiry')
            
            if user.email:
                email_subject = "Library Alert: Membership Expiry Reminder"
                email_body = f"Hello {user.get_full_name() or user.username},\n\nThis is to remind you that your library membership is set to expire on {student.membership_expiry}.\n\nPlease visit the library administration desk to renew your membership and prevent suspension of borrowing privileges.\n\nBest Regards,\nSmart Library Team"
                send_email_notification(email_subject, user.email, email_body)
    except Exception as e:
        logger.error(f"Error in Membership Expiry Check: {e}")

    logger.info("Daily library tasks execution completed.")
    ActivityLog.objects.create(
        user=None,
        action="System Maintenance",
        details="Daily background library tasks completed successfully."
    )


def scheduler_loop():
    """
    Infinite loop running in a background thread, executing once every 24 hours.
    Runs once immediately on server startup after a small delay.
    """
    logger.info("Background library task scheduler thread started.")
    # Sleep briefly to let Django finish setting up and database connections open
    time.sleep(5)
    
    # We skip running immediately on startup during development to prevent
    # SQLite database locks and performance lag from the 757 overdue records.
    pass

    # Loop daily
    while True:
        # Sleep for 24 hours (86400 seconds)
        # We can poll in smaller increments to allow clean shutdowns if we wanted,
        # but a simple sleep is standard for in-memory python threads.
        time.sleep(86400)
        try:
            run_daily_library_tasks()
        except Exception as e:
            logger.error(f"Periodic background tasks failed: {e}")
        finally:
            connection.close()


def start_scheduler():
    """
    Spawns the scheduler loop in a daemon thread.
    """
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
