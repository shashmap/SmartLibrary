from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from library.models import (
    CustomUser, Student, Faculty, Category, Book, BookCopy,
    BorrowRecord, Reservation, Fine, Notification, Announcement,
    FavouriteBook, Wishlist, BookReview, LibraryVisit, ActivityLog
)

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'phone', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'phone', 'profile_picture')}),
    )

class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'isbn', 'category', 'total_copies', 'available_copies', 'popularity_score']
    search_fields = ['title', 'author', 'isbn']
    list_filter = ['category']

class BookCopyAdmin(admin.ModelAdmin):
    list_display = ['copy_id', 'book', 'shelf_location', 'status']
    search_fields = ['copy_id', 'book__title']
    list_filter = ['status']

class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'book_copy', 'issue_date', 'due_date', 'return_date', 'status']
    search_fields = ['user__username', 'book_copy__copy_id', 'book_copy__book__title']
    list_filter = ['status', 'issue_date']

class FineAdmin(admin.ModelAdmin):
    list_display = ['borrow_record', 'amount', 'payment_status', 'paid_date']
    list_filter = ['payment_status']

class ReservationAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'reserve_date', 'expiry_date', 'status']
    list_filter = ['status']

# Register models
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Student)
admin.site.register(Faculty)
admin.site.register(Category)
admin.site.register(Book, BookAdmin)
admin.site.register(BookCopy, BookCopyAdmin)
admin.site.register(BorrowRecord, BorrowRecordAdmin)
admin.site.register(Reservation, ReservationAdmin)
admin.site.register(Fine, FineAdmin)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(FavouriteBook)
admin.site.register(Wishlist)
admin.site.register(BookReview)
admin.site.register(LibraryVisit)
admin.site.register(ActivityLog)
