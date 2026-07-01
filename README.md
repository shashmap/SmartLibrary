# SmartLibrary System - Project Documentation

## Introduction

While exploring different Library Management Systems, I noticed one common problem. Many systems allow users to issue and return books, but they don't automatically remind borrowers before the due date. As a result, students often forget to return books on time, receive unnecessary fines, and librarians have to manually follow up with borrowers.

To address this problem, I developed **SmartLibrary**, a modern campus library management platform that automates library operations while improving the experience for librarians, students, and faculty. Along with automated return reminders, the system provides QR code-based book identification, intelligent notifications, reservations, analytics dashboards, PDF report generation, and secure role-based access.

---

## 1. Project Technology Stack

The platform is designed with a lightweight, secure, and modern technology stack.

### Backend Engine

* **Framework:** Django 5.0.14 (Python 3.11.9)
* **Database:** SQLite 3 with optimized indexing for fast lookups
* **Background Processing:** Thread-safe daemon threads for overdue updates, reservation expirations, and membership warnings

### Frontend & Styling

* **Structure:** HTML5 with Django Template Language (DTL)
* **Styling:** CSS3 with a modern glassmorphic interface
* **Framework:** Bootstrap 5.3.2 & Bootstrap Icons
* **Typography:** Inter, Outfit, and Space Grotesk fonts
* **Charts:** Chart.js for interactive analytics

### Utility Libraries

* **PDF Generation:** ReportLab
* **QR Code Generation:** qrcode

---

# 2. Core User Roles

### Librarian (Admin)

* Manage books and categories
* Manage book copies
* View analytics
* Manage reservations
* Monitor fines
* Publish announcements

**Login Credentials**

* Username: `admin`
* Password: `admin`

### Students

Students can:

* Search books
* Borrow books
* Reserve unavailable books
* Add books to wishlist
* Pay fines
* View notifications

**Accounts**

* Username: `student1` to `student300`
* Password: `password`

### Faculty

Faculty members receive higher borrowing limits and priority renewals.

**Accounts**

* Username: `faculty1` to `faculty40`
* Password: `password`

---

# 3. Core Features

## Smart Book Catalog

* Manage books and categories
* Virtual book covers
* QR code generated automatically for every book
* Edit and delete book records

## Borrowing System

* Borrow available books
* Automatic status updates
* Return management
* Borrow history
* Email and in-app notifications

## Reservation System

When a book is unavailable, users can reserve it.

After a book is returned:

* The next reservation is automatically activated.
* Users receive notifications.
* Reservations expire automatically after three days if not collected.

## Automated Notification System

One of the key features of the project is the notification engine.

Users receive reminders for:

* Upcoming due dates
* Due today
* Overdue books
* Reservation availability
* New announcements

This helps reduce overdue returns and unnecessary fines.

## Fine Management

* ₹5 fine per overdue day
* Automatic fine calculation
* Payment tracking
* Fine history

## Campus Announcements

Librarians can publish announcements for:

* All users
* Students only
* Faculty only

Announcements appear instantly on user dashboards.

## Analytics Dashboard

Interactive dashboards display:

* Book category distribution
* Borrowing statistics
* Library activity
* Reservations
* Fine summaries

## PDF Reports

Generate reports for:

* Book Catalog
* Borrowing Logs
* Fine Audit Reports

---

# 4. System Workflow

1. User logs into the system.
2. Searches for a required book.
3. Borrows the available copy.
4. Notification confirms successful borrowing.
5. Due-date reminders are sent automatically.
6. If all copies are borrowed, the user can reserve the book.
7. Once returned, the next reservation is automatically activated.
8. Overdue books generate fines automatically.
9. Librarians monitor all activities through the dashboard.

---

# 5. Project Structure

### Important Files

* **models.py** – Database models
* **views.py** – Application logic
* **tasks.py** – Background scheduler
* **signals.py** – Automatic notifications
* **custom.css** – UI styling
* **base.html** – Main layout template

---

# 6. Benefits

* Reduces manual library work
* Prevents overdue returns through reminders
* Improves user experience
* Automates reservations and fine calculation
* Simplifies book tracking using QR codes
* Provides useful analytics for librarians
* Generates professional PDF reports

---

# 7. Conclusion

SmartLibrary is more than a traditional Library Management System. It combines automation, intelligent notifications, QR-based book management, analytics, reservations, and reporting into a single platform. By solving the common problem of missed return reminders while simplifying daily library operations, SmartLibrary provides a smarter and more efficient experience for both librarians and library users.

---

## 8. Setup & Running Instructions

To run the project on another machine:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/shashmap/SmartLibrary.git
   cd SmartLibrary
   ```

2. **Install dependencies**:
   Make sure you have Python (version 3.10+) installed. Run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**:
   Since the pre-seeded SQLite database (`db.sqlite3`) is already included in the repository, you do not need to run migrations or seed data. Simply start the local server:
   ```bash
   python manage.py runserver
   ```
   Open your browser and navigate to `http://127.0.0.1:8000/`.

4. **Downloading Reports**:
   Log in using the administrator account (`admin` / `admin`). Navigate to the **Reports Center** from the sidebar and click **Download PDF** on any of the reports. The system will compile the latest 200 logs and download the PDF report instantly.
