from django.urls import path
from library import views

urlpatterns = [
    # Auth
    path('', views.HomeView.as_view(), name='home'),
    path('login/', views.LoginViewCustom.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.LogoutViewCustom.as_view(), name='logout'),
    
    # Dashboards
    path('dashboard/', views.DashboardRedirectView.as_view(), name='dashboard'),
    path('dashboard/admin/', views.AdminDashboardView.as_view(), name='dashboard_admin'),
    path('dashboard/student/', views.StudentDashboardView.as_view(), name='dashboard_student'),
    path('dashboard/faculty/', views.FacultyDashboardView.as_view(), name='dashboard_faculty'),
    
    # Book Management
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('books/add/', views.BookCreateView.as_view(), name='book_create'),
    path('books/<int:pk>/edit/', views.BookUpdateView.as_view(), name='book_edit'),
    path('books/<int:pk>/delete/', views.BookDeleteView.as_view(), name='book_delete'),
    
    # Book Copy Management
    path('books/<int:book_id>/copy/add/', views.BookCopyCreateView.as_view(), name='copy_create'),
    path('books/<int:book_id>/copy/<int:pk>/delete/', views.BookCopyDeleteView.as_view(), name='copy_delete'),
    
    # Category Management
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<slug:slug>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('categories/<slug:slug>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # Transactions (Borrowing, Renewals, Returns)
    path('borrow/copy/<str:copy_id>/', views.BorrowBookActionView.as_view(), name='borrow_book'),
    path('borrow/return/<int:pk>/', views.ReturnBookActionView.as_view(), name='return_book'),
    path('borrow/renew/<int:pk>/', views.RenewBookActionView.as_view(), name='renew_book'),
    
    # Reservations
    path('reserve/book/<int:book_id>/', views.ReserveBookActionView.as_view(), name='reserve_book'),
    path('reserve/cancel/<int:pk>/', views.CancelReservationActionView.as_view(), name='cancel_reservation'),
    
    # Favorites & Wishlists
    path('books/<int:pk>/favorite/', views.ToggleFavoriteView.as_view(), name='toggle_favorite'),
    path('books/<int:pk>/wishlist/', views.ToggleWishlistView.as_view(), name='toggle_wishlist'),
    
    # Fines
    path('fines/', views.FineListView.as_view(), name='fine_list'),
    path('fines/pay/<int:pk>/', views.PayFineActionView.as_view(), name='pay_fine'),
    
    # Announcements
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/add/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<int:pk>/edit/', views.AnnouncementUpdateView.as_view(), name='announcement_edit'),
    path('announcements/<int:pk>/delete/', views.AnnouncementDeleteView.as_view(), name='announcement_delete'),
    
    # Profile & settings
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/password/', views.PasswordChangeViewCustom.as_view(), name='password_change'),
    
    # Reviews
    path('books/<int:book_id>/review/', views.BookReviewView.as_view(), name='book_review'),
    
    # Reports
    path('reports/', views.ReportsDashboardView.as_view(), name='reports'),
    path('reports/download/<str:report_type>/', views.DownloadReportPDFView.as_view(), name='download_report'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadView.as_view(), name='notification_read'),
    path('notifications/read-all/', views.MarkAllNotificationsReadView.as_view(), name='notifications_read_all'),
    
    # Search API
    path('api/books/search/', views.BookSearchAPIView.as_view(), name='api_book_search'),
]