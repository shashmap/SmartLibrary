from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from library.models import (
    BorrowRecord, Reservation, Fine, Book, Announcement, 
    FavouriteBook, CustomUser, BookCopy, ActivityLog
)
from library.notification_engine import send_notification, send_email_notification

@receiver(post_save, sender=BorrowRecord)
def handle_borrow_record_save(sender, instance, created, **kwargs):
    """
    Handles state transitions and notifications when a BorrowRecord is created or updated.
    """
    copy = instance.book_copy
    book = copy.book
    user = instance.user

    if created:
        # Mark the copy as borrowed
        copy.status = 'borrowed'
        copy.save()
        
        # Trigger Issue Notification
        title = "Book Issued Successfully"
        msg = f"You have successfully borrowed '{book.title}'. Due date: {instance.due_date}."
        send_notification(user, title, msg, 'issue')
        
        # Send Email
        if user.email:
            email_subject = "Library Alert: Book Issued"
            email_body = f"Hello {user.get_full_name() or user.username},\n\nYou have issued '{book.title}' by {book.author}.\nDue Date: {instance.due_date}\nShelf Location: {copy.shelf_location}\n\nPlease return it on or before the due date to avoid fines.\n\nBest Regards,\nSmart Library Team"
            send_email_notification(email_subject, user.email, email_body)
            
        ActivityLog.objects.create(
            user=user,
            action="Book Issued",
            details=f"Book: {book.title} | Copy ID: {copy.copy_id}"
        )

    else:
        # If updated to returned
        if instance.status == 'returned' and instance.return_date is not None:
            # First, check if there's any pending reservation for this book
            pending_res = Reservation.objects.filter(book=book, status='pending').order_index = 0
            # Wait, let's order by reservation date
            pending_res = Reservation.objects.filter(book=book, status='pending').order_by('reserve_date').first()
            
            if pending_res:
                # Mark copy as reserved for that user
                copy.status = 'reserved'
                copy.save()
                
                # Update reservation status to ready
                pending_res.status = 'ready'
                # Held for 3 days
                pending_res.expiry_date = timezone.localdate() + timedelta(days=3)
                pending_res.save()
                
                # Notify reservation user
                res_user = pending_res.user
                res_title = "Reserved Book Ready for Pickup"
                res_msg = f"The book '{book.title}' you reserved is now ready for pickup at shelf '{copy.shelf_location}'. This reservation is valid until {pending_res.expiry_date}."
                send_notification(res_user, res_title, res_msg, 'reservation')
                
                if res_user.email:
                    res_subject = "Library Alert: Reservation Ready for Pickup"
                    res_body = f"Hello {res_user.get_full_name() or res_user.username},\n\nGood news! The book '{book.title}' you reserved is now ready for pickup.\nShelf Location: {copy.shelf_location}\n\nPlease collect it by {pending_res.expiry_date}, after which the reservation will expire.\n\nBest Regards,\nSmart Library Team"
                    send_email_notification(res_subject, res_user.email, res_body)
            else:
                # Mark copy as available
                copy.status = 'available'
                copy.save()
            
            # Send return notification to the returning user
            title = "Book Returned Successfully"
            msg = f"You have successfully returned '{book.title}'. Thank you!"
            send_notification(user, title, msg, 'return')
            
            # Send return email
            if user.email:
                email_subject = "Library Alert: Book Returned"
                email_body = f"Hello {user.get_full_name() or user.username},\n\nWe have successfully received your return of '{book.title}'.\nReturn Date: {instance.return_date}\n\nThank you for using the Smart Library!\n\nBest Regards,\nSmart Library Team"
                send_email_notification(email_subject, user.email, email_body)
                
            ActivityLog.objects.create(
                user=user,
                action="Book Returned",
                details=f"Book: {book.title} | Copy ID: {copy.copy_id}"
            )


@receiver(post_save, sender=Fine)
def handle_fine_save(sender, instance, created, **kwargs):
    """
    Notifies users when a fine is generated or paid.
    """
    user = instance.borrow_record.user
    book_title = instance.borrow_record.book_copy.book.title

    if created:
        title = "New Fine Generated"
        msg = f"A fine of ₹{instance.amount} has been generated for overdue book '{book_title}'."
        send_notification(user, title, msg, 'fine')
        
        if user.email:
            email_subject = "Library Alert: Overdue Fine Generated"
            email_body = f"Hello {user.get_full_name() or user.username},\n\nYou have been fined Rs. {instance.amount} for the overdue book '{book_title}'.\n\nPlease return the book and clear your outstanding fine as soon as possible.\n\nBest Regards,\nSmart Library Team"
            send_email_notification(email_subject, user.email, email_body)
            
    elif instance.payment_status == 'paid' and instance.paid_date is not None:
        title = "Fine Paid Successfully"
        msg = f"Your fine of ₹{instance.amount} for '{book_title}' has been paid. Thank you!"
        send_notification(user, title, msg, 'fine')
        
        if user.email:
            email_subject = "Library Alert: Fine Payment Confirmed"
            email_body = f"Hello {user.get_full_name() or user.username},\n\nThis is to confirm that your payment of Rs. {instance.amount} for the overdue book '{book_title}' has been successfully received.\n\nThank you for clearing your dues.\n\nBest Regards,\nSmart Library Team"
            send_email_notification(email_subject, user.email, email_body)


@receiver(post_save, sender=Book)
def handle_new_book_save(sender, instance, created, **kwargs):
    """
    Notifies users of a new arrival if they have favorited books in this category.
    """
    if created:
        category = instance.category
        # Find users who have favorited books in this category, or have wishlist books in this category
        favorited_users = FavouriteBook.objects.filter(book__category=category).values_list('user', flat=True).distinct()
        
        for user_id in favorited_users:
            user = CustomUser.objects.filter(id=user_id).first()
            if user:
                title = "New Book in Your Favorite Category"
                msg = f"A new book '{instance.title}' by {instance.author} has been added to the {category.name} category."
                send_notification(user, title, msg, 'new_book')


@receiver(post_save, sender=Announcement)
def handle_announcement_save(sender, instance, created, **kwargs):
    """
    Broadcasts announcements to appropriate user categories.
    """
    if created:
        target = instance.target_role
        
        if target == 'all':
            users = CustomUser.objects.exclude(role='admin')
        elif target == 'student':
            users = CustomUser.objects.filter(role='student')
        elif target == 'faculty':
            users = CustomUser.objects.filter(role='faculty')
        else:
            users = []

        for user in users:
            send_notification(
                user=user,
                title=f"Announcement: {instance.title}",
                message=instance.content,
                notification_type='announcement'
            )
            
            # Send emails for announcements if users have email
            if user.email:
                email_subject = f"Library Announcement: {instance.title}"
                email_body = f"Hello {user.get_full_name() or user.username},\n\nThe library has published a new announcement:\n\n{instance.content}\n\nBest Regards,\nSmart Library Management System"
                # To prevent overloading background threads during seed data, we'll only send emails in real-time saves.
                # Since send_email_notification is fast (console output), we're fine.
                send_email_notification(email_subject, user.email, email_body)
