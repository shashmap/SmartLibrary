import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator

from library.models import (
    CustomUser, Student, Faculty, Category, Book, BookCopy, 
    BorrowRecord, Reservation, Fine, LibraryVisit, Notification, 
    BookReview, ActivityLog, Announcement, FavouriteBook, Wishlist
)
from library.forms import (
    LoginForm, BookForm, BookCopyForm, CategoryForm, AnnouncementForm, 
    BookReviewForm, UserRegistrationForm, StudentProfileForm, FacultyProfileForm, CustomUserForm
)
from library.services import (
    borrow_book, return_book_service, renew_book_service, 
    reserve_book_service, cancel_reservation_service
)
from library.utils import generate_pdf_report

# Access checks
def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)

class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        context = {
            'total_books': Book.objects.count(),
            'total_categories': Category.objects.count(),
            'total_members': CustomUser.objects.exclude(role='admin').count()
        }
        return render(request, 'library/home.html', context)

class LoginViewCustom(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'library/login.html', {'form': LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                ActivityLog.objects.create(user=user, action="Logged In")
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        return render(request, 'library/login.html', {'form': form})

class LogoutViewCustom(View):
    def get(self, request):
        if request.user.is_authenticated:
            ActivityLog.objects.create(user=request.user, action="Logged Out")
            logout(request)
            messages.success(request, "You have been logged out.")
        return redirect('login')

class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, 'library/register.html', {
            'form': UserRegistrationForm(),
            'student_form': StudentProfileForm(),
            'faculty_form': FacultyProfileForm()
        })

    def post(self, request):
        form = UserRegistrationForm(request.POST, request.FILES)
        role = request.POST.get('role', 'student')
        
        if role == 'student':
            profile_form = StudentProfileForm(request.POST)
        else:
            profile_form = FacultyProfileForm(request.POST)

        if form.is_valid() and profile_form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            
            ActivityLog.objects.create(user=user, action="Registered Account")
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been registered.")
            return redirect('dashboard')
            
        return render(request, 'library/register.html', {
            'form': form,
            'student_form': StudentProfileForm(request.POST) if role == 'student' else StudentProfileForm(),
            'faculty_form': FacultyProfileForm(request.POST) if role == 'faculty' else FacultyProfileForm()
        })

class DashboardRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role == 'admin':
            return redirect('dashboard_admin')
        elif request.user.role == 'student':
            return redirect('dashboard_student')
        elif request.user.role == 'faculty':
            return redirect('dashboard_faculty')
        return redirect('login')

class AdminDashboardView(AdminRequiredMixin, View):
    def get(self, request):
        total_fines_collected = Fine.objects.filter(payment_status='paid').aggregate(total=Sum('amount'))['total'] or 0
        total_fines_unpaid = Fine.objects.filter(payment_status='unpaid').aggregate(total=Sum('amount'))['total'] or 0
        
        # Category Book Distribution Chart
        categories = Category.objects.annotate(book_count=Count('books'))
        labels = [c.name for c in categories]
        data = [c.book_count for c in categories]
        chart_data_json = json.dumps({'labels': labels, 'data': data})
        
        # Recent active/overdue loans query
        recent_loans = BorrowRecord.objects.filter(status__in=['active', 'overdue']).select_related('book_copy__book', 'user').order_by('-issue_date')[:5]
        
        context = {
            'total_books': Book.objects.count(),
            'total_users': CustomUser.objects.exclude(role='admin').count(),
            'active_loans': BorrowRecord.objects.filter(status='active').count(),
            'overdue_loans': BorrowRecord.objects.filter(status='overdue').count(),
            'total_fines_collected': total_fines_collected,
            'total_fines_unpaid': total_fines_unpaid,
            'pending_reservations': Reservation.objects.filter(status='pending').count(),
            'activities': ActivityLog.objects.all().order_by('-timestamp')[:5],
            'recent_loans': recent_loans,
            'top_readers': CustomUser.objects.exclude(role='admin').annotate(borrow_count=Count('borrow_records')).order_by('-borrow_count')[:5],
            'chart_data_json': chart_data_json
        }
        return render(request, 'library/dashboard_admin.html', context)

class StudentDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'student':
            return redirect('dashboard')
        
        active_loans = BorrowRecord.objects.filter(user=request.user, status__in=['active', 'overdue']).select_related('book_copy__book')
        total_unpaid_fine = Fine.objects.filter(borrow_record__user=request.user, payment_status='unpaid').aggregate(total=Sum('amount'))['total'] or 0
        reservations = Reservation.objects.filter(user=request.user, status__in=['pending', 'ready']).select_related('book')
        fines = Fine.objects.filter(borrow_record__user=request.user).select_related('borrow_record__book_copy__book')
        announcements = Announcement.objects.filter(target_role__in=['all', 'student']).order_by('-created_at')[:5]
        recommendations = Book.objects.all().order_by('-popularity_score')[:4]
        
        context = {
            'active_loans': active_loans,
            'total_unpaid_fine': total_unpaid_fine,
            'reservations': reservations,
            'fines': fines,
            'announcements': announcements,
            'recommendations': recommendations
        }
        return render(request, 'library/dashboard_student.html', context)

class FacultyDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.role != 'faculty':
            return redirect('dashboard')
            
        active_loans = BorrowRecord.objects.filter(user=request.user, status__in=['active', 'overdue']).select_related('book_copy__book')
        total_unpaid_fine = Fine.objects.filter(borrow_record__user=request.user, payment_status='unpaid').aggregate(total=Sum('amount'))['total'] or 0
        reservations = Reservation.objects.filter(user=request.user, status__in=['pending', 'ready']).select_related('book')
        fines = Fine.objects.filter(borrow_record__user=request.user).select_related('borrow_record__book_copy__book')
        announcements = Announcement.objects.filter(target_role__in=['all', 'faculty']).order_by('-created_at')[:5]
        recommendations = Book.objects.all().order_by('-popularity_score')[:4]
        
        context = {
            'active_loans': active_loans,
            'total_unpaid_fine': total_unpaid_fine,
            'reservations': reservations,
            'fines': fines,
            'announcements': announcements,
            'recommendations': recommendations
        }
        return render(request, 'library/dashboard_faculty.html', context)

class BookListView(View):
    def get(self, request):
        q = request.GET.get('q', '')
        category_slug = request.GET.get('category', '')
        
        books = Book.objects.all().select_related('category')
        if q:
            books = books.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q))
        if category_slug:
            books = books.filter(category__slug=category_slug)
            
        paginator = Paginator(books, 8)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'books': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'categories': Category.objects.all(),
            'selected_category': category_slug,
            'search_query': q
        }
        return render(request, 'library/book_list.html', context)

class BookDetailView(View):
    def get(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        copies = book.copies.all()
        reviews = book.reviews.all().select_related('user')
        
        is_favorite = False
        is_wishlisted = False
        has_active_borrow = False
        has_pending_reservation = False
        
        if request.user.is_authenticated:
            is_favorite = FavouriteBook.objects.filter(user=request.user, book=book).exists()
            is_wishlisted = Wishlist.objects.filter(user=request.user, book=book).exists()
            has_active_borrow = BorrowRecord.objects.filter(user=request.user, book_copy__book=book, status__in=['active', 'overdue']).exists()
            has_pending_reservation = Reservation.objects.filter(user=request.user, book=book, status__in=['pending', 'ready']).exists()
            
        context = {
            'book': book,
            'copies': copies,
            'reviews': reviews,
            'review_form': BookReviewForm(),
            'is_favorite': is_favorite,
            'is_wishlisted': is_wishlisted,
            'has_active_borrow': has_active_borrow,
            'has_pending_reservation': has_pending_reservation
        }
        return render(request, 'library/book_detail.html', context)

class BookCreateView(AdminRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('book_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Book created successfully!")
        return super().form_valid(form)

class BookUpdateView(AdminRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('book_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Book updated successfully!")
        return super().form_valid(form)

class BookDeleteView(AdminRequiredMixin, DeleteView):
    model = Book
    template_name = 'library/book_confirm_delete.html'
    success_url = reverse_lazy('book_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Book deleted successfully!")
        return super().form_valid(form)

class BookCopyCreateView(AdminRequiredMixin, View):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        return render(request, 'library/copy_form.html', {'form': BookCopyForm(), 'book': book})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        form = BookCopyForm(request.POST)
        if form.is_valid():
            copy = form.save(commit=False)
            copy.book = book
            copy.save()
            messages.success(request, f"Book copy {copy.copy_id} added.")
            return redirect('book_detail', pk=book.id)
        return render(request, 'library/copy_form.html', {'form': form, 'book': book})

class BookCopyDeleteView(AdminRequiredMixin, View):
    def get(self, request, book_id, pk):
        copy = get_object_or_404(BookCopy, pk=pk)
        return render(request, 'library/copy_confirm_delete.html', {'copy': copy})

    def post(self, request, book_id, pk):
        copy = get_object_or_404(BookCopy, pk=pk)
        copy.delete()
        messages.success(request, "Book copy deleted successfully.")
        return redirect('book_detail', pk=book_id)

class CategoryListView(AdminRequiredMixin, ListView):
    model = Category
    template_name = 'library/category_list.html'
    context_object_name = 'categories'

class CategoryCreateView(AdminRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('category_list')

class CategoryUpdateView(AdminRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library/category_form.html'
    success_url = reverse_lazy('category_list')

class CategoryDeleteView(AdminRequiredMixin, DeleteView):
    model = Category
    template_name = 'library/category_confirm_delete.html'
    success_url = reverse_lazy('category_list')

# Transaction Action Views
class BorrowBookActionView(LoginRequiredMixin, View):
    def post(self, request, copy_id):
        success, msg = borrow_book(request.user, copy_id)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('dashboard')))

class ReturnBookActionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        record = get_object_or_404(BorrowRecord, pk=pk)
        success, msg = return_book_service(record.book_copy.copy_id)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('dashboard')))

class RenewBookActionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        success, msg = renew_book_service(request.user, pk)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('dashboard')))

class ReserveBookActionView(LoginRequiredMixin, View):
    def post(self, request, book_id):
        success, msg = reserve_book_service(request.user, book_id)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('dashboard')))

class CancelReservationActionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        success, msg = cancel_reservation_service(request.user, pk)
        if success:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('dashboard')))

class ToggleFavoriteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        fav, created = FavouriteBook.objects.get_or_create(user=request.user, book=book)
        if not created:
            fav.delete()
            messages.success(request, f"Removed '{book.title}' from Favorites.")
        else:
            messages.success(request, f"Added '{book.title}' to Favorites.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('book_detail', kwargs={'pk': pk})))

class ToggleWishlistView(LoginRequiredMixin, View):
    def post(self, request, pk):
        book = get_object_or_404(Book, pk=pk)
        wish, created = Wishlist.objects.get_or_create(user=request.user, book=book)
        if not created:
            wish.delete()
            messages.success(request, f"Removed '{book.title}' from Wishlist.")
        else:
            messages.success(request, f"Added '{book.title}' to Wishlist.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('book_detail', kwargs={'pk': pk})))

class FineListView(LoginRequiredMixin, View):
    def get(self, request):
        if is_admin(request.user):
            fines = Fine.objects.all().select_related('borrow_record__user', 'borrow_record__book_copy__book')
        else:
            fines = Fine.objects.filter(borrow_record__user=request.user).select_related('borrow_record__book_copy__book')
        return render(request, 'library/fine_list.html', {'fines': fines})

class PayFineActionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        fine = get_object_or_404(Fine, pk=pk)
        fine.payment_status = 'paid'
        fine.paid_date = timezone.localdate()
        fine.save()
        messages.success(request, f"Fine of ₹{fine.amount} paid successfully.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('fine_list')))

class AnnouncementListView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'library/announcement_list.html'
    context_object_name = 'announcements'

class AnnouncementCreateView(AdminRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'library/announcement_form.html'
    success_url = reverse_lazy('announcement_list')

class AnnouncementUpdateView(AdminRequiredMixin, UpdateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'library/announcement_form.html'
    success_url = reverse_lazy('announcement_list')

class AnnouncementDeleteView(AdminRequiredMixin, DeleteView):
    model = Announcement
    template_name = 'library/announcement_list.html'
    success_url = reverse_lazy('announcement_list')

class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        student = getattr(request.user, 'student_profile', None)
        faculty = getattr(request.user, 'faculty_profile', None)
        return render(request, 'library/profile.html', {
            'student': student,
            'faculty': faculty
        })

class ProfileEditView(LoginRequiredMixin, View):
    def get(self, request):
        user_form = CustomUserForm(instance=request.user)
        if request.user.role == 'student':
            profile_form = StudentProfileForm(instance=getattr(request.user, 'student_profile', None))
        else:
            profile_form = FacultyProfileForm(instance=getattr(request.user, 'faculty_profile', None))
            
        return render(request, 'library/profile_edit.html', {
            'user_form': user_form,
            'profile_form': profile_form
        })

    def post(self, request):
        user_form = CustomUserForm(request.POST, request.FILES, instance=request.user)
        if request.user.role == 'student':
            profile_form = StudentProfileForm(request.POST, instance=getattr(request.user, 'student_profile', None))
        else:
            profile_form = FacultyProfileForm(request.POST, instance=getattr(request.user, 'faculty_profile', None))

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
            
        return render(request, 'library/profile_edit.html', {
            'user_form': user_form,
            'profile_form': profile_form
        })

class PasswordChangeViewCustom(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'library/password_change.html', {'form': PasswordChangeForm(request.user)})

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Password changed successfully! Please log in again.")
            return redirect('login')
        return render(request, 'library/password_change.html', {'form': form})

class BookReviewView(LoginRequiredMixin, View):
    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        form = BookReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.book = book
            review.save()
            messages.success(request, "Review submitted successfully.")
        return redirect('book_detail', pk=book_id)

class ReportsDashboardView(AdminRequiredMixin, View):
    def get(self, request):
        return render(request, 'library/reports.html')

class DownloadReportPDFView(AdminRequiredMixin, View):
    def get(self, request, report_type):
        try:
            pdf_bytes = generate_pdf_report(report_type)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
            return response
        except Exception as e:
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect('reports')

class NotificationListView(LoginRequiredMixin, View):
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'library/notification_list.html', {'notifications': notifications})

class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save()
        return JsonResponse({'status': 'success'})

class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('notification_list')

class BookSearchAPIView(View):
    def get(self, request):
        q = request.GET.get('q', '')
        if len(q) < 2:
            return JsonResponse({'books': []})
        books = Book.objects.filter(Q(title__icontains=q) | Q(author__icontains=q))[:5]
        data = [{'id': b.id, 'title': b.title, 'author': b.author} for b in books]
        return JsonResponse({'books': data})
