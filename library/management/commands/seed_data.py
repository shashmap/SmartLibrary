import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction, models

from library.models import (
    CustomUser, Student, Faculty, Category, Book, BookCopy,
    BorrowRecord, Reservation, Fine, Notification, BookReview,
    LibraryVisit, ActivityLog, Announcement, FavouriteBook, Wishlist
)
from library.recommendation_engine import update_books_statistics

class Command(BaseCommand):
    help = "Seeds the database with realistic demo data"

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding...")
        
        # 1. Clean existing library data (preserve superusers if they exist, but delete profiles)
        self.stdout.write("Cleaning existing database...")
        ActivityLog.objects.all().delete()
        LibraryVisit.objects.all().delete()
        BookReview.objects.all().delete()
        Notification.objects.all().delete()
        Announcement.objects.all().delete()
        Fine.objects.all().delete()
        BorrowRecord.objects.all().delete()
        Reservation.objects.all().delete()
        BookCopy.objects.all().delete()
        Book.objects.all().delete()
        Category.objects.all().delete()
        
        # Keep superusers if they exist, delete all student/faculty CustomUsers
        CustomUser.objects.filter(role__in=['student', 'faculty']).delete()
        
        # Ensure default Admin account exists
        admin_user, created = CustomUser.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@library.local',
                'first_name': 'Library',
                'last_name': 'Admin',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'password': make_password('admin')
            }
        )
        if not created:
            admin_user.password = make_password('admin')
            admin_user.role = 'admin'
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write("Reset default admin credentials to admin/admin")
        else:
            self.stdout.write("Created default admin credentials (admin/admin)")

        # 2. Seed 25 Categories
        categories_data = [
            ("Computer Science", "CS and programming subjects"),
            ("Mathematics", "Algebra, calculus, and mathematical studies"),
            ("Physics", "Mechanics, quantum physics, and relativity"),
            ("Chemistry", "Organic, inorganic, and physical chemistry"),
            ("Biology", "Genetics, ecology, and evolutionary biology"),
            ("History", "Ancient and modern world history"),
            ("Literature", "Classic novels and modern literature works"),
            ("Philosophy", "Metaphysics, ethics, and epistemology"),
            ("Economics", "Macroeconomics, microeconomics, and finance theory"),
            ("Psychology", "Cognitive psychology and behavioral sciences"),
            ("Sociology", "Study of human society and relationships"),
            ("Political Science", "Government systems and political analysis"),
            ("Engineering", "Mechanical, electrical, and civil engineering"),
            ("Medicine", "Anatomy, pharmacology, and clinical practice"),
            ("Art & Design", "Fine arts, digital design, and architecture history"),
            ("Law", "Constitutional law, criminal law, and jurisprudence"),
            ("Education", "Pedagogy and teaching methodologies"),
            ("Business & Finance", "Corporate strategy and investment banking"),
            ("Anthropology", "Human evolution and cultural studies"),
            ("Astronomy", "Astrophysics and cosmological study of space"),
            ("Geography", "Physical geography and human cartography"),
            ("Drama & Theater", "Playwriting, stagecraft, and theater history"),
            ("Poetry", "Anthologies of classic and modern poems"),
            ("Linguistics", "Syntax, semantics, and language development"),
            ("Environmental Science", "Climate studies, conservation, and ecology")
        ]
        
        categories = []
        for name, desc in categories_data:
            cat = Category(name=name, description=desc)
            cat.save()  # Call save to auto-slugify
            categories.append(cat)
            
        self.stdout.write(f"Seeded {len(categories)} categories.")

        # 3. Seed 1000 Books
        self.stdout.write("Generating 1000 books...")
        authors = [
            "Alan Turing", "Richard Feynman", "Albert Einstein", "Stephen Hawking", "Ada Lovelace",
            "Donald Knuth", "Grace Hopper", "Charles Darwin", "Sigmund Freud", "Adam Smith",
            "Karl Marx", "Plato", "Aristotle", "Friedrich Nietzsche", "Jean-Paul Sartre",
            "George Orwell", "Jane Austen", "William Shakespeare", "F. Scott Fitzgerald", "Ernest Hemingway",
            "Mark Twain", "Virginia Woolf", "Leo Tolstoy", "Fyodor Dostoevsky", "Gabriel Garcia Marquez",
            "J.K. Rowling", "Isaac Asimov", "Arthur C. Clarke", "Philip K. Dick", "H.P. Lovecraft",
            "J.R.R. Tolkien", "George R.R. Martin", "Stephen King", "Agatha Christie", "Edgar Allan Poe",
            "Haruki Murakami", "Albert Camus", "Franz Kafka", "Aldous Huxley", "Ray Bradbury",
            "Carl Sagan", "Neil deGrasse Tyson", "Yuval Noah Harari", "Noam Chomsky", "Thomas Piketty",
            "Daniel Kahneman", "Malcolm Gladwell", "Steve Jobs", "Bill Gates", "Tim Berners-Lee"
        ]
        
        publishers = [
            "O'Reilly Media", "Pearson Education", "McGraw-Hill", "Oxford University Press",
            "Springer Science", "Penguin Books", "HarperCollins", "Macmillan Publishers",
            "Simon & Schuster", "Hachette Book Group", "MIT Press", "Cambridge University Press",
            "Wiley-Blackwell", "Routledge", "Elsevier"
        ]
        
        book_prefixes = [
            "Introduction to", "Advanced", "Principles of", "Foundations of", "The Art of",
            "Understanding", "A History of", "A Modern Approach to", "Elements of", "Handbook of",
            "Exploring", "Introduction to the Study of", "Theoretical", "Applied", "Guide to"
        ]
        
        book_suffixes = [
            "Vol. 1", "Second Edition", "for Beginners", "and its Applications", "in Theory and Practice",
            "with Case Studies", "for Professionals", "and Systems", "and Design", "Methods"
        ]

        books = []
        isbns_created = set()
        
        for i in range(1000):
            cat = random.choice(categories)
            prefix = random.choice(book_prefixes)
            suffix = random.choice(book_suffixes)
            
            title = f"{prefix} {cat.name} {suffix}"
            if i % 10 == 0:
                title = f"The {cat.name} Anthology"
            elif i % 7 == 0:
                title = f"Classic Readings in {cat.name}"
                
            author = random.choice(authors)
            publisher = random.choice(publishers)
            
            # Generate unique 13 digit ISBN
            while True:
                isbn = f"978{random.randint(1000000000, 9999999999)}"
                if isbn not in isbns_created:
                    isbns_created.add(isbn)
                    break
            
            pub_date = timezone.localdate() - timedelta(days=random.randint(100, 5000))
            desc = f"A comprehensive resource covering major topics in {cat.name}. Ideal for academic study, research, and general interest reading."
            
            book = Book(
                title=title,
                author=author,
                isbn=isbn,
                publisher=publisher,
                publication_date=pub_date,
                category=cat,
                description=desc,
                total_copies=0,
                available_copies=0
            )
            books.append(book)

        # Bulk create books (Need to save one-by-one or do post-create for QR codes because custom save has qrcode logic.
        # But wait! Generating 1000 QR codes on startup takes time. We can bypass generating QR code files during seed
        # to make it fast, or seed it in chunks.
        # Actually, let's bulk create the books. Since bulk_create doesn't call save(), QR codes won't be generated instantly.
        # That's perfectly fine! They will be generated dynamically on first save/update, or we can write a quick QR code generator
        # loop. Let's bulk create the Books first.
        Book.objects.bulk_create(books)
        # Fetch them back to get IDs
        seeded_books = list(Book.objects.all())
        self.stdout.write("Seeded 1000 book metadata records.")

        # 4. Seed Book Copies
        self.stdout.write("Generating physical copies (BookCopy) for books...")
        copies = []
        locations = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2", "F1", "F2", "G1", "G2"]
        
        copy_counter = 1
        for book in seeded_books:
            # Let's give each book 1 to 4 copies
            num_copies = random.randint(1, 4)
            for j in range(num_copies):
                copy_id = f"CP-{book.id:04d}-{j+1}"
                loc = f"Shelf {random.choice(locations)}"
                copy = BookCopy(
                    book=book,
                    copy_id=copy_id,
                    shelf_location=loc,
                    status='available'
                )
                copies.append(copy)
                
        BookCopy.objects.bulk_create(copies)
        
        # Now update the copies counts for all books
        for book in seeded_books:
            book.update_copies_count()
            
        seeded_copies = list(BookCopy.objects.all())
        self.stdout.write(f"Seeded {len(seeded_copies)} physical book copies.")

        # 5. Seed Users (300 Students and 40 Faculty)
        self.stdout.write("Generating 300 Students and 40 Faculty...")
        student_users = []
        faculty_users = []
        password_hash = make_password('password')
        
        departments = ["Computer Science", "Electrical Engineering", "Mechanical Engineering", "Physics", "Mathematics", "Business Administration", "Literature", "Chemistry"]
        
        # Students CustomUser objects
        for i in range(1, 301):
            user = CustomUser(
                username=f"student{i}",
                first_name=f"Student",
                last_name=f"User {i}",
                email=f"student{i}@library.local",
                role='student',
                password=password_hash
            )
            student_users.append(user)
            
        # Faculty CustomUser objects
        for i in range(1, 41):
            user = CustomUser(
                username=f"faculty{i}",
                first_name=f"Faculty",
                last_name=f"Member {i}",
                email=f"faculty{i}@library.local",
                role='faculty',
                password=password_hash
            )
            faculty_users.append(user)
            
        # Bulk create Users
        CustomUser.objects.bulk_create(student_users)
        CustomUser.objects.bulk_create(faculty_users)
        
        # Fetch back created users
        all_students = list(CustomUser.objects.filter(role='student'))
        all_faculty = list(CustomUser.objects.filter(role='faculty'))
        
        # Create student profiles
        student_profiles = []
        for idx, user in enumerate(all_students):
            roll_number = f"STU2026{idx+1:03d}"
            dept = random.choice(departments)
            expiry = timezone.localdate() + timedelta(days=random.randint(180, 720))
            profile = Student(
                user=user,
                roll_number=roll_number,
                department=dept,
                max_borrow_limit=5,
                membership_expiry=expiry
            )
            student_profiles.append(profile)
            
        Student.objects.bulk_create(student_profiles)
        
        # Create faculty profiles
        faculty_profiles = []
        for idx, user in enumerate(all_faculty):
            emp_id = f"FAC2026{idx+1:03d}"
            dept = random.choice(departments)
            profile = Faculty(
                user=user,
                employee_id=emp_id,
                department=dept,
                max_borrow_limit=10,
                research_interest=f"Advanced research in {dept} domains and multidisciplinary fields."
            )
            faculty_profiles.append(profile)
            
        Faculty.objects.bulk_create(faculty_profiles)
        
        self.stdout.write("Created student and faculty profiles.")

        # 6. Seed Borrow Records (15,000 records)
        self.stdout.write("Generating 15,000 Borrow Records...")
        borrow_records = []
        fines_to_create = []
        
        all_borrower_users = all_students + all_faculty
        
        # We need historical records spanning the last 365 days
        today = timezone.localdate()
        
        # Prepare list of random book copies to pick from
        # To make it realistic, some book copies will be highly borrowed (popular)
        # We assign copies to a weight
        weighted_copies = seeded_copies
        
        # We can split the 15000 records
        # 85% returned
        # 12% active
        # 3% overdue
        num_returned = 12750
        num_active = 1800
        num_overdue = 450
        
        # Generate Returned Borrows
        self.stdout.write("Generating returned records...")
        for i in range(num_returned):
            user = random.choice(all_borrower_users)
            copy = random.choice(weighted_copies)
            
            # Dates
            issue_d = today - timedelta(days=random.randint(30, 365))
            duration = 14 if user.role == 'student' else 30
            due_d = issue_d + timedelta(days=duration)
            
            # Return date: mostly returned on time, occasionally late
            if random.random() < 0.90:
                # Returned on time or early
                return_d = issue_d + timedelta(days=random.randint(1, duration))
            else:
                # Returned late (overdue fine generated!)
                overdue_days = random.randint(1, 20)
                return_d = due_d + timedelta(days=overdue_days)
                
            record = BorrowRecord(
                user=user,
                book_copy=copy,
                issue_date=issue_d,
                due_date=due_d,
                return_date=return_d,
                status='returned',
                renewal_count=random.randint(0, 2)
            )
            borrow_records.append(record)
            
        # We bulk create returned records in chunks of 5000 to keep memory low
        BorrowRecord.objects.bulk_create(borrow_records)
        
        # Clear the memory list and query back the records that generated fines
        borrow_records = []
        
        # Generate Fines for returned records
        self.stdout.write("Generating fines for returned records...")
        returned_late_records = BorrowRecord.objects.filter(status='returned', return_date__gt=models.F('due_date'))
        fines = []
        for record in returned_late_records:
            overdue_days = (record.return_date - record.due_date).days
            amount = overdue_days * 0.50
            # 90% chance the fine was paid
            paid = random.random() < 0.90
            fine = Fine(
                borrow_record=record,
                amount=amount,
                payment_status='paid' if paid else 'unpaid',
                paid_date=record.return_date if paid else None
            )
            fines.append(fine)
            if len(fines) >= 2000:
                Fine.objects.bulk_create(fines)
                fines = []
        if fines:
            Fine.objects.bulk_create(fines)

        # Let's generate Active Borrows (1800 records)
        # These will mark the respective copies as 'borrowed'
        self.stdout.write("Generating active records...")
        active_records = []
        borrowed_copies = set()
        
        for i in range(num_active):
            user = random.choice(all_borrower_users)
            
            # Find an available copy
            # Limit the search to avoid long loops
            copy = None
            for _ in range(10):
                c = random.choice(weighted_copies)
                if c.id not in borrowed_copies:
                    copy = c
                    break
            
            if not copy:
                continue
                
            borrowed_copies.add(copy.id)
            
            duration = 14 if user.role == 'student' else 30
            # Issued within last 'duration' days, so it's not overdue yet
            issue_d = today - timedelta(days=random.randint(0, duration - 1))
            due_d = issue_d + timedelta(days=duration)
            
            record = BorrowRecord(
                user=user,
                book_copy=copy,
                issue_date=issue_d,
                due_date=due_d,
                status='active',
                renewal_count=random.randint(0, 1)
            )
            active_records.append(record)
            
        BorrowRecord.objects.bulk_create(active_records)

        # Generate Overdue Borrows (450 records)
        self.stdout.write("Generating overdue records...")
        overdue_records_list = []
        for i in range(num_overdue):
            user = random.choice(all_borrower_users)
            
            copy = None
            for _ in range(10):
                c = random.choice(weighted_copies)
                if c.id not in borrowed_copies:
                    copy = c
                    break
                    
            if not copy:
                continue
                
            borrowed_copies.add(copy.id)
            
            duration = 14 if user.role == 'student' else 30
            # Issued older than 'duration' days
            issue_d = today - timedelta(days=random.randint(duration + 1, duration + 40))
            due_d = issue_d + timedelta(days=duration)
            
            record = BorrowRecord(
                user=user,
                book_copy=copy,
                issue_date=issue_d,
                due_date=due_d,
                status='overdue',
                renewal_count=0
            )
            overdue_records_list.append(record)
            
        BorrowRecord.objects.bulk_create(overdue_records_list)
        
        # Now update copy statuses in the database for the active and overdue borrowings
        # We gather their BookCopy IDs
        active_copy_ids = BorrowRecord.objects.filter(status='active').values_list('book_copy_id', flat=True)
        overdue_copy_ids = BorrowRecord.objects.filter(status='overdue').values_list('book_copy_id', flat=True)
        
        BookCopy.objects.filter(id__in=active_copy_ids).update(status='borrowed')
        BookCopy.objects.filter(id__in=overdue_copy_ids).update(status='borrowed')
        
        # Create outstanding fines for current overdue records
        self.stdout.write("Generating fines for current overdue records...")
        current_overdues = BorrowRecord.objects.filter(status='overdue')
        unpaid_fines = []
        for record in current_overdues:
            overdue_days = (today - record.due_date).days
            amount = overdue_days * 0.50
            fine = Fine(
                borrow_record=record,
                amount=amount,
                payment_status='unpaid',
                paid_date=None
            )
            unpaid_fines.append(fine)
            
        Fine.objects.bulk_create(unpaid_fines)
        
        # Re-update copy counts and scores for all books
        for book in Book.objects.all():
            book.update_copies_count()

        self.stdout.write(f"Borrow records and fines successfully seeded.")

        # 7. Seed Reservations (2000 records)
        self.stdout.write("Generating 2000 Reservations...")
        reservations = []
        # Find books with 0 available copies
        unavailable_books = list(Book.objects.filter(available_copies=0))
        if not unavailable_books:
            unavailable_books = seeded_books
            
        statuses = ['pending', 'ready', 'completed', 'cancelled', 'expired']
        weights = [0.15, 0.05, 0.40, 0.20, 0.20] # weights corresponding to status distribution
        
        for i in range(2000):
            user = random.choice(all_borrower_users)
            book = random.choice(unavailable_books)
            status = random.choices(statuses, weights=weights, k=1)[0]
            
            res_date = today - timedelta(days=random.randint(1, 100))
            exp_date = None
            if status in ['ready', 'expired']:
                exp_date = res_date + timedelta(days=3)
                
            res = Reservation(
                user=user,
                book=book,
                reserve_date=res_date,
                expiry_date=exp_date,
                status=status
            )
            reservations.append(res)
            
        Reservation.objects.bulk_create(reservations)
        self.stdout.write("Seeded 2000 Reservation records.")

        # 8. Seed Notifications (1000 records)
        self.stdout.write("Generating 1000 Notifications...")
        notifications = []
        notification_types = ['issue', 'return', 'due_warning', 'overdue', 'reservation', 'new_book', 'fine', 'expiry', 'announcement']
        titles = {
            'issue': "Book Issued Successfully",
            'return': "Book Returned Successfully",
            'due_warning': "Reminder: Book Due Soon",
            'overdue': "URGENT: Overdue Book Alert",
            'reservation': "Reserved Book Ready",
            'new_book': "New Book in Favorite Category",
            'fine': "Fine Notice Issued",
            'expiry': "Membership Expiring Soon",
            'announcement': "Library Holiday Announcement"
        }
        
        for i in range(1000):
            user = random.choice(all_borrower_users)
            n_type = random.choice(notification_types)
            created_d = timezone.now() - timedelta(days=random.randint(1, 30), hours=random.randint(1, 23))
            
            notif = Notification(
                user=user,
                title=titles[n_type],
                message=f"This is a automated notification message of type {n_type} for demonstration purposes.",
                notification_type=n_type,
                is_read=random.choice([True, False, True]), # 2/3 chance read
                created_at=created_d
            )
            notifications.append(notif)
            
        Notification.objects.bulk_create(notifications)
        self.stdout.write("Seeded 1000 Notification records.")

        # 9. Seed Reviews (500 records)
        self.stdout.write("Generating 500 Reviews...")
        reviews = []
        review_comments = [
            "Highly informative and well structured.",
            "A bit dense, but extremely thorough and comprehensive.",
            "Excellent introduction. Helped me ace my examinations!",
            "Great resource for researchers. Found the case studies helpful.",
            "The explanations are very clear. Highly recommended.",
            "A classic! Every student in the department should read this.",
            "Useful reference book. Keep it on your bookshelf.",
            "Standard textbook. Good content but a bit dry.",
            "Outdated in some parts, but the fundamental theories are solid.",
            "Absolutely loved the layout and explanations."
        ]
        
        for i in range(500):
            user = random.choice(all_borrower_users)
            book = random.choice(seeded_books)
            
            # Check if this user already reviewed this book to avoid errors
            rev = BookReview(
                user=user,
                book=book,
                rating=random.randint(3, 5), # mostly positive reviews
                review_text=random.choice(review_comments),
                created_at=timezone.now() - timedelta(days=random.randint(1, 150))
            )
            reviews.append(rev)
            
        BookReview.objects.bulk_create(reviews)
        self.stdout.write("Seeded 500 Review records.")

        # 10. Seed Favourites and Wishlists for recommendations testing
        self.stdout.write("Generating Favourites and Wishlist items...")
        favs = []
        wishes = []
        fav_pairs = set()
        wish_pairs = set()
        
        for user in all_borrower_users[:150]: # create for a subset to save time
            # Give 2-5 favorites
            for _ in range(random.randint(2, 5)):
                book = random.choice(seeded_books)
                pair = (user.id, book.id)
                if pair not in fav_pairs:
                    fav_pairs.add(pair)
                    favs.append(FavouriteBook(user=user, book=book))
                    
            # Give 1-3 wishlist items
            for _ in range(random.randint(1, 3)):
                book = random.choice(seeded_books)
                pair = (user.id, book.id)
                if pair not in wish_pairs:
                    wish_pairs.add(pair)
                    wishes.append(Wishlist(user=user, book=book))
                    
        FavouriteBook.objects.bulk_create(favs)
        Wishlist.objects.bulk_create(wishes)

        # 11. Seed some Announcements (5 records)
        self.stdout.write("Seeding announcements...")
        announcements_data = [
            ("Summer Break Operating Hours", "Dear members, please note that the library will operate from 9:00 AM to 5:00 PM during the summer break (July 1st to August 15th). Normal hours will resume on August 16th.", "all"),
            ("New Digital Subscriptions", "We are pleased to announce new campus-wide access to IEEE Xplore and Nature Journals. Log in using institutional single sign-on.", "all"),
            ("Thesis Submission Deadline", "Attention Faculty Members: Please submit your list of department research book requirements for the upcoming semester by next Friday.", "faculty"),
            ("Late Return Fine Waived on Holidays", "Fines will not be calculated for books whose due dates fall during the upcoming Winter holidays (Dec 24th - Jan 2nd).", "all"),
            ("Study Room Booking Rules", "Students are reminded that study rooms can be reserved for a maximum of 2 hours per day. Bookings can be made at the circulation desk.", "student")
        ]
        for title, content, target in announcements_data:
            Announcement.objects.create(title=title, content=content, target_role=target)

        # 12. Preprocessing statistics (calculate recommendation scores, etc.)
        self.stdout.write("Running AI statistics preprocessor...")
        update_books_statistics()

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
