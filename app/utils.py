"""
Utility functions for the Cinema POS system
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import qrcode
from PIL import Image as PILImage
import tempfile
import base64

def generate_ticket_pdf(booking_data):
    """
    Generate a PDF ticket for a booking
    
    Args:
        booking_data (dict): Dictionary containing booking information
        
    Returns:
        bytes: PDF data as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    normal_style = styles['Normal']
    
    # Cinema Title
    elements.append(Paragraph("CINEMA POS", title_style))
    elements.append(Paragraph("MOVIE TICKET", heading_style))
    elements.append(Spacer(1, 20))
    
    # Generate QR Code
    qr_data = f"Booking ID: {booking_data.get('id', 'N/A')}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create QR code image in memory
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes and then to ReportLab Image
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    # Create ReportLab Image from bytes
    from reportlab.lib.utils import ImageReader
    qr_img = ImageReader(img_bytes)
    
    # Add booking details
    details = [
        ["Booking ID:", f"#{booking_data.get('id', 'N/A')}"],
        ["Customer:", booking_data.get('customer_name', 'N/A')],
        ["Movie:", booking_data.get('movie_title', 'N/A')],
        ["Screen:", booking_data.get('screen_name', 'N/A')],
        ["Date:", booking_data.get('show_date', 'N/A')],
        ["Time:", booking_data.get('show_time', 'N/A')],
        ["Seats:", booking_data.get('seats', 'N/A')],
        ["Amount:", f"₹{booking_data.get('total_amount', '0.00')}"],
    ]
    
    # Create details table
    details_table = Table(details, colWidths=[1.5*inch, 3*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    # Create main ticket table
    ticket_table = Table([
        [qr_img, details_table]
    ], colWidths=[2.5*inch, 4.5*inch])
    
    ticket_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(ticket_table)
    elements.append(Spacer(1, 20))
    
    # Add terms and conditions
    elements.append(Paragraph("Terms & Conditions:", heading_style))
    terms = [
        "1. Please arrive 15 minutes before the show starts.",
        "2. This ticket is non-refundable and non-transferable.",
        "3. Outside food and beverages are not allowed.",
        "4. Please present this ticket at the entrance.",
        "5. Management reserves the right of admission."
    ]
    
    for term in terms:
        elements.append(Paragraph(term, normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data


def generate_receipt_pdf(payment_data):
    """
    Generate a PDF receipt for a payment
    
    Args:
        payment_data (dict): Dictionary containing payment information
        
    Returns:
        bytes: PDF data as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkgreen
    )
    
    normal_style = styles['Normal']
    
    # Cinema Title
    elements.append(Paragraph("CINEMA POS", title_style))
    elements.append(Paragraph("PAYMENT RECEIPT", heading_style))
    elements.append(Spacer(1, 20))
    
    # Receipt details
    receipt_details = [
        ["Receipt ID:", f"#RCP-{payment_data.get('id', 'N/A')}-{datetime.now().strftime('%Y%m%d')}"],
        ["Payment Date:", payment_data.get('payment_date', datetime.now()).strftime('%d %b %Y %H:%M')],
        ["Payment Method:", payment_data.get('payment_method', 'N/A').title()],
        ["Transaction ID:", payment_data.get('transaction_id', 'N/A')],
        ["Status:", "Completed"],
    ]
    
    receipt_table = Table(receipt_details, colWidths=[2*inch, 4*inch])
    receipt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(receipt_table)
    elements.append(Spacer(1, 20))
    
    # Customer information
    elements.append(Paragraph("Customer Information", heading_style))
    
    customer_details = [
        ["Name:", payment_data.get('customer_name', 'N/A')],
        ["Contact:", payment_data.get('contact_number', 'N/A')],
        ["Email:", payment_data.get('email', 'N/A')],
        ["Booking ID:", f"#{payment_data.get('booking_id', 'N/A')}"],
    ]
    
    customer_table = Table(customer_details, colWidths=[2*inch, 4*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(customer_table)
    elements.append(Spacer(1, 20))
    
    # Booking details
    elements.append(Paragraph("Booking Details", heading_style))
    
    booking_details = [
        ["Movie", "Screen", "Date & Time", "Seats", "Amount"],
        [
            payment_data.get('movie_title', 'N/A'),
            payment_data.get('screen_name', 'N/A'),
            f"{payment_data.get('show_date', 'N/A')} {payment_data.get('show_time', 'N/A')}",
            payment_data.get('seats', 'N/A'),
            f"₹{payment_data.get('amount', '0.00')}"
        ]
    ]
    
    booking_table = Table(booking_details, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch, 1*inch])
    booking_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, 1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(booking_table)
    elements.append(Spacer(1, 20))
    
    # Total amount
    total_details = [
        ["", "", "Total Amount:", f"₹{payment_data.get('amount', '0.00')}"]
    ]
    
    total_table = Table(total_details, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    elements.append(total_table)
    elements.append(Spacer(1, 30))
    
    # Footer
    elements.append(Paragraph("Thank you for your business!", normal_style))
    elements.append(Paragraph("This is a computer-generated receipt and does not require a signature.", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data


def generate_report_pdf(report_data, report_type):
    """
    Generate a PDF report
    
    Args:
        report_data (dict): Dictionary containing report information
        report_type (str): Type of report (daily_sales, occupancy, cashier_summary)
        
    Returns:
        bytes: PDF data as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.5*inch, rightMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.darkblue
    )
    
    normal_style = styles['Normal']
    
    # Report Title
    if report_type == 'daily_sales':
        title = "DAILY SALES REPORT"
    elif report_type == 'occupancy':
        title = "SEAT OCCUPANCY REPORT"
    elif report_type == 'cashier_summary':
        title = "CASHIER PERFORMANCE SUMMARY"
    else:
        title = "REPORT"
    
    elements.append(Paragraph("CINEMA POS", title_style))
    elements.append(Paragraph(title, heading_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %b %Y %H:%M')}", normal_style))
    elements.append(Spacer(1, 20))
    
    # Add summary cards if available
    if 'summary' in report_data:
        summary = report_data['summary']
        
        # Create summary table
        summary_data = []
        for key, value in summary.items():
            summary_data.append([key.replace('_', ' ').title(), str(value)])
        
        if summary_data:
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(summary_table)
            elements.append(Spacer(1, 20))
    
    # Add detailed data table if available
    if 'data' in report_data and report_data['data']:
        data = report_data['data']
        
        # Create table headers based on report type
        if report_type == 'daily_sales':
            headers = ['Time', 'Movie', 'Screen', 'Show', 'Bookings', 'Tickets', 'Revenue', 'Occupancy']
        elif report_type == 'occupancy':
            headers = ['Date', 'Screen', 'Movie', 'Show Time', 'Total Seats', 'Seats Sold', 'Occupancy', 'Revenue']
        elif report_type == 'cashier_summary':
            headers = ['Cashier', 'Bookings', 'Tickets Sold', 'Revenue', 'Avg Transaction', 'Refunds', 'Net Revenue']
        else:
            headers = list(data[0].keys()) if data else []
        
        # Create table data
        table_data = [headers]
        
        for item in data:
            row = []
            for header in headers:
                key = header.lower().replace(' ', '_')
                if key in item:
                    value = item[key]
                    # Format currency values
                    if 'revenue' in key or 'amount' in key or 'transaction' in key:
                        if isinstance(value, (int, float)):
                            row.append(f"₹{value:.2f}")
                        else:
                            row.append(str(value))
                    # Format percentage values
                    elif 'occupancy' in key:
                        if isinstance(value, (int, float)):
                            row.append(f"{value:.1f}%")
                        else:
                            row.append(str(value))
                    else:
                        row.append(str(value))
                else:
                    row.append("N/A")
            table_data.append(row)
        
        # Create table
        table = Table(table_data)
        
        # Style the table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        # Alternate row colors
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.lightgrey),
                ]))
        
        elements.append(table)
    
    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("End of Report", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generate_payment_receipt_pdf(receipt_data):
    """
    Generate a PDF receipt for a payment with enhanced details
    
    Args:
        receipt_data (dict): Dictionary containing payment receipt information
        
    Returns:
        bytes: PDF data as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Container for 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkgreen
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.darkgreen
    )
    
    normal_style = styles['Normal']
    
    # Cinema Title
    elements.append(Paragraph("CINEMA POS", title_style))
    elements.append(Paragraph("PAYMENT RECEIPT", heading_style))
    elements.append(Spacer(1, 20))
    
    # Receipt details
    receipt_details = [
        ["Receipt ID:", receipt_data.get('receipt_id', 'N/A')],
        ["Payment Date:", receipt_data.get('payment_date', 'N/A')],
        ["Payment Method:", receipt_data.get('payment_method', 'N/A')],
        ["Transaction ID:", receipt_data.get('transaction_id', 'N/A')],
        ["Status:", receipt_data.get('status', 'N/A')],
    ]
    
    receipt_table = Table(receipt_details, colWidths=[2*inch, 4*inch])
    receipt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(receipt_table)
    elements.append(Spacer(1, 20))
    
    # Customer information
    elements.append(Paragraph("Customer Information", heading_style))
    
    customer_details = [
        ["Name:", receipt_data.get('customer_name', 'N/A')],
        ["Contact:", receipt_data.get('customer_contact', 'N/A')],
        ["Email:", receipt_data.get('customer_email', 'N/A')],
        ["Booking ID:", receipt_data.get('booking_id', 'N/A')],
    ]
    
    customer_table = Table(customer_details, colWidths=[2*inch, 4*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(customer_table)
    elements.append(Spacer(1, 20))
    
    # Payment method specific details
    paypal_info = receipt_data.get('paypal_info', {})
    if paypal_info:
        elements.append(Paragraph("PayPal Payment Details", heading_style))
        
        paypal_details = []
        if paypal_info.get('order_id'):
            paypal_details.append(["PayPal Order ID:", paypal_info['order_id']])
        if paypal_info.get('capture_id'):
            paypal_details.append(["PayPal Capture ID:", paypal_info['capture_id']])
        if paypal_info.get('payment_status'):
            paypal_details.append(["PayPal Status:", paypal_info['payment_status']])
        
        if paypal_details:
            paypal_table = Table(paypal_details, colWidths=[2*inch, 4*inch])
            paypal_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (1, 0), (1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(paypal_table)
            elements.append(Spacer(1, 20))
    
    card_info = receipt_data.get('card_info', {})
    if card_info:
        elements.append(Paragraph("Card Payment Details", heading_style))
        
        card_details = [
            ["Card Type:", card_info.get('card_type', 'N/A')],
            ["Card Number:", f"****-****-****-{card_info.get('card_last_4', 'N/A')}" if card_info.get('card_last_4') else 'N/A'],
            ["Expiry:", card_info.get('expiry', 'N/A')],
            ["Auth Code:", card_info.get('auth_code', 'N/A')],
        ]
        
        card_table = Table(card_details, colWidths=[2*inch, 4*inch])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(card_table)
        elements.append(Spacer(1, 20))
    
    upi_info = receipt_data.get('upi_info', {})
    if upi_info:
        elements.append(Paragraph("UPI Payment Details", heading_style))
        
        upi_details = [
            ["UPI ID:", upi_info.get('upi_id', 'N/A')],
            ["Transaction ID:", upi_info.get('transaction_id', 'N/A')],
            ["UTR Number:", upi_info.get('utr_number', 'N/A')],
        ]
        
        upi_table = Table(upi_details, colWidths=[2*inch, 4*inch])
        upi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(upi_table)
        elements.append(Spacer(1, 20))
    
    # Booking details
    elements.append(Paragraph("Booking Details", heading_style))
    
    booking_details = [
        ["Movie", "Screen", "Date & Time", "Seats", "Amount"],
        [
            receipt_data.get('movie_title', 'N/A'),
            receipt_data.get('screen_name', 'N/A'),
            f"{receipt_data.get('show_date', 'N/A')} {receipt_data.get('show_time', 'N/A')}",
            receipt_data.get('seats', 'N/A'),
            f"₹{receipt_data.get('amount', '0.00')}"
        ]
    ]
    
    booking_table = Table(booking_details, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch, 1*inch])
    booking_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, 1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(booking_table)
    elements.append(Spacer(1, 20))
    
    # Total amount
    total_details = [
        ["", "", "Total Amount:", f"₹{receipt_data.get('amount', '0.00')}"]
    ]
    
    total_table = Table(total_details, colWidths=[2*inch, 1.5*inch, 2*inch, 1.5*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    elements.append(total_table)
    elements.append(Spacer(1, 20))
    
    # Refund information if applicable
    refund_info = receipt_data.get('refund_info', {})
    if refund_info:
        elements.append(Paragraph("Refund Information", heading_style))
        
        refund_details = [
            ["Refund Amount:", f"₹{refund_info.get('refund_amount', '0.00')}"],
            ["Refund Reason:", refund_info.get('refund_reason', 'N/A')],
            ["Refund Method:", refund_info.get('refund_method', 'N/A')],
            ["Refund Reference:", refund_info.get('refund_reference', 'N/A')],
        ]
        
        if refund_info.get('refund_notes'):
            refund_details.append(["Refund Notes:", refund_info['refund_notes']])
        
        refund_table = Table(refund_details, colWidths=[2*inch, 4*inch])
        refund_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (1, 0), (1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(refund_table)
        elements.append(Spacer(1, 20))
    
    # Notes if applicable
    if receipt_data.get('notes'):
        elements.append(Paragraph("Notes", heading_style))
        elements.append(Paragraph(receipt_data['notes'], normal_style))
        elements.append(Spacer(1, 20))
    
    # Footer
    elements.append(Paragraph("Thank you for your business!", normal_style))
    elements.append(Paragraph("This is a computer-generated receipt and does not require a signature.", normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data