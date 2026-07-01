from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from library.models import Book, BorrowRecord, FavouriteBook, Wishlist, Category

def update_books_statistics():
    """
    Recalculates and updates the popularity and availability scores for all books.
    Can be run as part of daily maintenance or seeding.
    """
    books = Book.objects.all()
    if not books.exists():
        return
        
    # Get the maximum borrow count across all books to normalize popularity
    # We annotate each book with the number of times it has been borrowed
    borrow_counts = Book.objects.annotate(
        total_borrows=Count('copies__borrows')
    )
    max_borrows = max([b.total_borrows for b in borrow_counts] or [1])
    if max_borrows == 0:
        max_borrows = 1

    for book in books:
        # Update availability score
        book.update_copies_count()
        
        # Calculate popularity score (normalized 0.0 to 10.0 scale)
        actual_borrows = BorrowRecord.objects.filter(book_copy__book=book).count()
        book.popularity_score = round((actual_borrows / max_borrows) * 10.0, 2)
        book.save()


def get_ai_recommendations(user, limit=6):
    """
    Generates personalized book recommendations for a user.
    Uses multi-factor scoring based on:
    - Favorite Categories (explicit: FavouriteBook category)
    - Borrow History (implicit categories)
    - Previously Read Books (demoted to promote discovery, unless favorited)
    - Currently Borrowed (filtered out)
    - Trending (borrow count in last 30 days)
    - Recency (added in last 30 days)
    - General Popularity and Availability scores
    
    Handles cold start by returning trending and popular books.
    """
    # 1. Get user data
    user_fav_categories = set()
    user_borrowed_categories = {}
    user_read_book_ids = set()
    user_current_book_ids = set()

    if user.is_authenticated:
        # Get categories of user's favorite books
        fav_books = FavouriteBook.objects.filter(user=user).select_related('book__category')
        for fb in fav_books:
            user_fav_categories.add(fb.book.category_id)
            
        # Get wishlist categories too
        wishlist_books = Wishlist.objects.filter(user=user).select_related('book__category')
        for wb in wishlist_books:
            user_fav_categories.add(wb.book.category_id)

        # Get user's complete borrowing history
        borrow_records = BorrowRecord.objects.filter(user=user).select_related('book_copy__book')
        for record in borrow_records:
            book_id = record.book_copy.book_id
            cat_id = record.book_copy.book.category_id
            
            if record.status in ['active', 'overdue']:
                user_current_book_ids.add(book_id)
            else:
                user_read_book_ids.add(book_id)
                
            user_borrowed_categories[cat_id] = user_borrowed_categories.get(cat_id, 0) + 1

    # 2. Get all books (excluding currently borrowed ones)
    books_query = Book.objects.all()
    if user_current_book_ids:
        books_query = books_query.exclude(id__in=user_current_book_ids)
        
    books = list(books_query.select_related('category'))
    
    # 3. Calculate trending counts (borrows in the last 30 days)
    thirty_days_ago = timezone.localdate() - timedelta(days=30)
    trending_borrows = BorrowRecord.objects.filter(
        issue_date__gte=thirty_days_ago
    ).values('book_copy__book_id').annotate(count=Count('id'))
    
    trending_map = {item['book_copy__book_id']: item['count'] for item in trending_borrows}
    max_trending = max(trending_map.values() or [1])

    # 4. Score each book
    scored_books = []
    for book in books:
        score = 0.0
        
        # Factor A: Favorite Categories (Explicit Interest)
        if book.category_id in user_fav_categories:
            score += 5.0
            
        # Factor B: Borrow History (Implicit Interest)
        category_borrows = user_borrowed_categories.get(book.category_id, 0)
        if category_borrows > 0:
            score += min(category_borrows * 1.5, 7.5) # Cap category boost at 7.5 points
            
        # Factor C: Previously Read (Promote discovery of unread books)
        if book.id in user_read_book_ids:
            # Check if they also favorited it (if so, keep it high; if not, demote)
            has_fav = FavouriteBook.objects.filter(user=user, book=book).exists()
            if not has_fav:
                score -= 3.0 # Soft demotion for already read but not favorited
            else:
                score += 1.0 # Slight boost for favorite read books (user likes to re-read)
                
        # Factor D: Trending Books (Popularity in last 30 days)
        trending_count = trending_map.get(book.id, 0)
        if trending_count > 0:
            score += (trending_count / max_trending) * 4.0
            
        # Factor E: Recently Added (New arrivals)
        # If the book was published/added recently (let's assume based on ID for simplicity, or publication date)
        # We can check publication_date if available
        if book.publication_date:
            three_months_ago = timezone.localdate() - timedelta(days=90)
            if book.publication_date >= three_months_ago:
                score += 2.0
                
        # Factor F: General Popularity (Lifetime borrow normalized score 0-10)
        score += book.popularity_score * 0.5 # Adds up to 5 points
        
        # Factor G: Availability (Prioritize available books)
        score += book.availability_score * 1.5 # Adds up to 1.5 points
        
        scored_books.append((book, score))
        
    # 5. Sort by score descending and return the top books
    scored_books.sort(key=lambda x: x[1], reverse=True)
    
    return [book for book, score in scored_books[:limit]]
