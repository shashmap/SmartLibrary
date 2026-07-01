import io
from django.utils import timezone
from django.db.models import Count, Sum
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from library.models import Book, BorrowRecord, Fine, Student, Faculty, CustomUser, Category

def generate_pdf_report(report_type, start_date=None, end_date=None):
    """
    Generates a professionally styled PDF report based on report_type.
    Returns a BytesIO buffer containing the PDF data.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1e293b'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER,
        spaceAfter=25
    )
    
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    right_cell_style = ParagraphStyle(
        'TableRightCell',
        parent=cell_style,
        alignment=TA_RIGHT
    )

    story = []
    date_str = timezone.now().strftime("%B %d, %Y %I:%M %p")
    
    if report_type == 'books':
        story.append(Paragraph("Smart Library System - Book Catalog Report", title_style))
        story.append(Paragraph(f"Generated on: {date_str}", subtitle_style))
        
        books = Book.objects.all().select_related('category').order_by('title')
        
        data = [[
            Paragraph("<b>Title</b>", header_style),
            Paragraph("<b>Author</b>", header_style),
            Paragraph("<b>ISBN</b>", header_style),
            Paragraph("<b>Category</b>", header_style),
            Paragraph("<b>Copies (Avail)</b>", header_style)
        ]]
        
        for b in books:
            data.append([
                Paragraph(b.title, cell_style),
                Paragraph(b.author, cell_style),
                Paragraph(b.isbn, cell_style),
                Paragraph(b.category.name, cell_style),
                Paragraph(f"{b.total_copies} ({b.available_copies})", cell_style)
            ])
            
        t = Table(data, colWidths=[160, 110, 90, 110, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t)
        
    elif report_type == 'loans' or report_type == 'borrowings':
        story.append(Paragraph("Smart Library System - Borrowing Logs Report", title_style))
        story.append(Paragraph(f"Generated on: {date_str}", subtitle_style))
        
        loans = BorrowRecord.objects.all().select_related('user', 'book_copy__book').order_by('-issue_date')
        
        data = [[
            Paragraph("<b>User</b>", header_style),
            Paragraph("<b>Book Copy</b>", header_style),
            Paragraph("<b>Issue Date</b>", header_style),
            Paragraph("<b>Due Date</b>", header_style),
            Paragraph("<b>Status</b>", header_style)
        ]]
        
        for l in loans:
            data.append([
                Paragraph(l.user.username, cell_style),
                Paragraph(f"{l.book_copy.book.title} ({l.book_copy.copy_id})", cell_style),
                Paragraph(str(l.issue_date), cell_style),
                Paragraph(str(l.due_date), cell_style),
                Paragraph(l.get_status_display(), cell_style)
            ])
            
        t = Table(data, colWidths=[100, 200, 80, 80, 70])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t)
        
    elif report_type == 'fines':
        story.append(Paragraph("Smart Library System - Fines Audit Report", title_style))
        story.append(Paragraph(f"Generated on: {date_str}", subtitle_style))
        
        fines = Fine.objects.all().select_related('borrow_record__user', 'borrow_record__book_copy__book').order_by('-borrow_record__issue_date')
        
        data = [[
            Paragraph("<b>User</b>", header_style),
            Paragraph("<b>Book</b>", header_style),
            Paragraph("<b>Fine Amount</b>", header_style),
            Paragraph("<b>Status</b>", header_style),
            Paragraph("<b>Paid Date</b>", header_style)
        ]]
        
        for f in fines:
            data.append([
                Paragraph(f.borrow_record.user.username, cell_style),
                Paragraph(f.borrow_record.book_copy.book.title, cell_style),
                Paragraph(f"Rs. {f.amount}", cell_style),
                Paragraph(f.get_payment_status_display(), cell_style),
                Paragraph(str(f.paid_date or "-"), cell_style)
            ])
            
        t = Table(data, colWidths=[100, 200, 80, 70, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t)
        
    else:
        story.append(Paragraph("Smart Library System - System Report", title_style))
        story.append(Paragraph(f"Generated on: {date_str}", subtitle_style))
        story.append(Paragraph("Empty report details provided.", cell_style))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()