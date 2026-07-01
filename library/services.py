from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.conf import settings
from library.models import (
    Book, BookCopy, BorrowRecord, Reservation, 
    Student, Faculty, ActivityLog, Fine
)

def get_user_borrow_limit(user):
    """
    Returns the maximum borrow limit for the user based on their profile role.
    """
    if user.role == 'student':
        try:
            return user.student_profile.max_borrow_limit
        except Student.DoesNotExist:
            return getattr(settings, 'STUDENT_MAX_BORROW_LIMIT', 5)
    elif user.role == 'faculty':
        try:
            return user.faculty_profile.max_borrow_limit
        except Faculty.DoesNotExist:
            return getattr(settings, 'FACULTY_MAX_BORROW_LIMIT', 10)
    return 0


def get_user_borrow_duration(user):
    """
    Returns the borrowing duration in days based on user role.
    """
    if user.role == 'student':
        return getattr(settings, 'STUDENT_BORROW_DAYS', 14)
    elif user.role == 'faculty':
        return getattr(settings, 'FACULTY_BORROW_DAYS', 30)
    return 14


def borrow_book(user, copy_id):
    """
    Issues a book copy to a user, checking limits and availability.
    """
    try:
        copy = BookCopy.objects.get(copy_id=copy_id)
    except BookCopy.DoesNotExist:
        return False, "Book copy not found."

    if copy.status != 'available':
        # If it is reserved, check if it is reserved for THIS user
        if copy.status == 'reserved':
            res = Reservation.objects.filter(
                book=copy.book, user=user, status='ready'
            ).first()
            if not res:
                return False, "This copy is reserved for another user."
        else:
            return False, f"Book copy is not available (Status: {copy.get_status_display()})."

    # Enforce borrow limits
    limit = get_user_borrow_limit(user)
    active_borrows = BorrowRecord.objects.filter(user=user, status__in=['active', 'overdue']).count()
    if active_borrows >= limit:
        return False, f"You have reached your maximum borrow limit of {limit} books."

    # Prevent borrowing if they have outstanding unpaid fines
    unpaid_fines = Fine.objects.filter(borrow_record__user=user, payment_status='unpaid').exists()
    if unpaid_fines:
        return False, "You have unpaid fines. Please clear your fines before borrowing new books."

    # Perform checkout in a transaction
    with transaction.atomic():
        # Check if there was a reservation for this book by this user that was ready
        ready_res = Reservation.objects.filter(
            book=copy.book, user=user, status='ready'
        ).first()
        if ready_res:
            ready_res.status = 'completed'
            ready_res.save()

        # Create borrow record
        duration = get_user_borrow_duration(user)
        due_date = timezone.localdate() + timedelta(days=duration)
        
        record = BorrowRecord.objects.create(
            user=user,
            book_copy=copy,
            due_date=due_date,
            status='active'
        )

    return True, f"Book '{copy.book.title}' issued successfully. Due date: {due_date}."


def return_book_service(copy_id):
    """
    Returns a book copy, updating the borrow record and triggering return logic.
    """
    try:
        copy = BookCopy.objects.get(copy_id=copy_id)
    except BookCopy.DoesNotExist:
        return False, "Book copy not found."

    record = BorrowRecord.objects.filter(
        book_copy=copy, 
        status__in=['active', 'overdue']
    ).first()

    if not record:
        return False, "No active borrow record found for this copy."

    with transaction.atomic():
        # Set return details
        record.return_date = timezone.localdate()
        record.status = 'returned'
        record.save()
        
        # Calculate final fine if overdue at return time
        # The daily task calculates fines periodically, but let's lock it in on return
        if record.return_date > record.due_date:
            fine_rate = getattr(settings, 'FINE_RATE_PER_DAY', 5.00)
            overdue_days = (record.return_date - record.due_date).days
            fine_amount = overdue_days * fine_rate
            
            fine, created = Fine.objects.get_or_create(
                borrow_record=record,
                payment_status='unpaid'
            )
            fine.amount = fine_amount
            fine.save()

    return True, f"Book '{copy.book.title}' returned successfully."


def renew_book_service(user, record_id):
    """
    Renews an active borrow record if allowed.
    Conditions:
    1. Maximum of 2 renewals.
    2. Cannot renew if there are active reservations on the book.
    3. Cannot renew if already overdue.
    """
    try:
        record = BorrowRecord.objects.get(id=record_id, user=user)
    except BorrowRecord.DoesNotExist:
        return False, "Borrow record not found."

    if record.status != 'active':
        if record.status == 'overdue':
            return False, "Overdue books cannot be renewed. Please return the book and clear outstanding fines."
        return False, "Only active borrowings can be renewed."

    if record.renewal_count >= 2:
        return False, "You have reached the maximum of 2 renewals for this book."

    # Check for reservations on this book
    book = record.book_copy.book
    has_reservations = Reservation.objects.filter(book=book, status='pending').exists()
    if has_reservations:
        return False, "This book has been reserved by another user and cannot be renewed."

    # Process renewal
    duration = get_user_borrow_duration(user)
    record.due_date = record.due_date + timedelta(days=duration)
    record.renewal_count += 1
    record.save()

    ActivityLog.objects.create(
        user=user,
        action="Book Renewed",
        details=f"Book: {book.title} | New Due Date: {record.due_date}"
    )

    return True, f"Book renewed successfully. New due date: {record.due_date}."


def reserve_book_service(user, book_id):
    """
    Creates a pending reservation for a user on a book.
    Only allowed if all copies of the book are currently unavailable (borrowed/reserved/maintenance).
    """
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return False, "Book not found."

    # If the user already has an active borrow record for this book, prevent reservation
    already_borrowed = BorrowRecord.objects.filter(
        user=user, book_copy__book=book, status__in=['active', 'overdue']
    ).exists()
    if already_borrowed:
        return False, "You already have an active checkout of this book."

    # If the user already has a pending or ready reservation for this book, prevent duplicate
    already_reserved = Reservation.objects.filter(
        user=user, book=book, status__in=['pending', 'ready']
    ).exists()
    if already_reserved:
        return False, "You already have a reservation for this book."

    # If there are available copies, user should borrow instead
    available_copies = book.copies.filter(status='available').count()
    if available_copies > 0:
        return False, "Copies of this book are currently available. Please borrow instead."

    # Create reservation
    res = Reservation.objects.create(
        user=user,
        book=book,
        status='pending'
    )

    ActivityLog.objects.create(
        user=user,
        action="Book Reserved",
        details=f"Book: {book.title} (Reservation ID: {res.id})"
    )

    return True, f"Book '{book.title}' reserved successfully."


def cancel_reservation_service(user, reservation_id):
    """
    Cancels a reservation. If the reservation was 'ready', releases the copy.
    """
    try:
        res = Reservation.objects.get(id=reservation_id, user=user)
    except Reservation.DoesNotExist:
        return False, "Reservation not found."

    if res.status not in ['pending', 'ready']:
        return False, "This reservation cannot be cancelled."

    old_status = res.status
    book = res.book

    with transaction.atomic():
        res.status = 'cancelled'
        res.save()

        # If it was ready, there is a physical copy held (copy.status = 'reserved')
        if old_status == 'ready':
            copy = BookCopy.objects.filter(book=book, status='reserved').first()
            if copy:
                # Check if there is another pending reservation in the queue
                next_res = Reservation.objects.filter(book=book, status='pending').order_by('reserve_date').first()
                if next_res:
                    next_res.status = 'ready'
                    next_res.expiry_date = timezone.localdate() + timedelta(days=3)
                    next_res.save()
                    
                    # Notify user
                    next_user = next_res.user
                    from library.notification_engine import send_notification, send_email_notification
                    res_title = "Reserved Book Ready for Pickup"
                    res_msg = f"The book '{book.title}' you reserved is now ready for pickup at shelf '{copy.shelf_location}'."
                    send_notification(next_user, res_title, res_msg, 'reservation')
                    
                    if next_user.email:
                        res_subject = "Library Alert: Reservation Ready for Pickup"
                        res_body = f"Hello {next_user.get_full_name() or next_user.username},\n\nThe book '{book.title}' is ready for pickup.\n\nBest Regards,\nSmart Library Team"
                        send_email_notification(res_subject, next_user.email, res_body)
                else:
                    # Mark copy available
                    copy.status = 'available'
                    copy.save()

    ActivityLog.objects.create(
        user=user,
        action="Reservation Cancelled",
        details=f"Book: {book.title}"
    )

    return True, "Reservation cancelled successfully."
