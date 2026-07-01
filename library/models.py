import os
import qrcode
from io import BytesIO
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.files import File
from django.utils import timezone
from django.utils.text import slugify

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin/Librarian'),
        ('student', 'Student'),
        ('faculty', 'Faculty'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def is_admin(self):
        return self.role == 'admin' or self.is_superuser

    def is_student(self):
        return self.role == 'student'

    def is_faculty(self):
        return self.role == 'faculty'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Student(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    roll_number = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    max_borrow_limit = models.IntegerField(default=5)
    membership_expiry = models.DateField()

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.roll_number}"


class Faculty(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='faculty_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    max_borrow_limit = models.IntegerField(default=10)
    research_interest = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.employee_id}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, unique=True)
    publisher = models.CharField(max_length=255)
    publication_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='books')
    cover_image = models.ImageField(blank=True, null=True, upload_to='book_covers/')
    qr_code = models.ImageField(blank=True, null=True, upload_to='qr_codes/')
    total_copies = models.IntegerField(default=0)
    available_copies = models.IntegerField(default=0)
    popularity_score = models.FloatField(default=0.0)
    availability_score = models.FloatField(default=1.0)

    def save(self, *args, **kwargs):
        # Save book to get ID if needed
        super().save(*args, **kwargs)
        if not self.qr_code:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(f"/books/{self.id}/")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            filename = f"qr_{self.isbn}.png"
            self.qr_code.save(filename, File(buffer), save=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class BookCopy(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Maintenance'),
    ]
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='copies')
    copy_id = models.CharField(max_length=50, unique=True)
    shelf_location = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')

    class Meta:
        verbose_name_plural = "Book Copies"

    def __str__(self):
        return f"{self.book.title} ({self.copy_id})"


class BorrowRecord(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]
    book_copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, related_name='borrows')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='borrow_records')
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    return_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    renewal_count = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} borrowed {self.book_copy.copy_id}"


class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('ready', 'Ready'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reservations')
    reserve_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Reservation of {self.book.title} by {self.user.username}"


class Fine(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    borrow_record = models.ForeignKey(BorrowRecord, on_delete=models.CASCADE, related_name='fines')
    amount = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    paid_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Fine of ₹{self.amount} for {self.borrow_record.user.username}"


class LibraryVisit(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='visits')
    check_in_time = models.DateTimeField(default=timezone.now)
    check_out_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-check_in_time']

    def __str__(self):
        return f"{self.user.username} visit on {self.check_in_time.strftime('%Y-%m-%d')}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('issue', 'Book Issued'),
        ('return', 'Book Returned'),
        ('due_warning', 'Due Reminder'),
        ('overdue', 'Overdue Alert'),
        ('reservation', 'Reservation Available'),
        ('new_book', 'New Arrival'),
        ('fine', 'Fine Notification'),
        ('expiry', 'Membership Expiry'),
        ('announcement', 'Announcement'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification: {self.title} for {self.user.username}"


class BookReview(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')])
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review on {self.book.title} by {self.user.username}"


class ActivityLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='activities')
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} by {self.user.username if self.user else 'System'}"


class Announcement(models.Model):
    ROLE_TARGETS = [
        ('all', 'All Users'),
        ('student', 'Students Only'),
        ('faculty', 'Faculty Only'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    target_role = models.CharField(max_length=20, choices=ROLE_TARGETS, default='all')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class FavouriteBook(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='favorites')
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'book')

    def __str__(self):
        return f"{self.user.username} favorited {self.book.title}"


class Wishlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wishlist')
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'book')

    def __str__(self):
        return f"{self.user.username} wishlisted {self.book.title}"