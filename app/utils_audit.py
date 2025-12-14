"""
Additional utility functions for payment audit PDF generation
This is a temporary file to add the audit PDF function without modifying the existing utils.py
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


class ConcurrentAccessChecker:
    """Utility class for checking concurrent access conflicts"""
    
    @staticmethod
    def check_booking_conflicts(show_id, seat_ids, user_id):
        """
        Check for booking conflicts with concurrent access
        
        Args:
            show_id (int): ID of the show
            seat_ids (list): List of seat IDs to check
            user_id (int): ID of the current user
            
        Returns:
            dict: Dictionary with conflict information
        """
        # For now, just return no conflicts
        # In a real implementation, this would check the database for existing bookings/locks
        return {
            'has_conflict': False,
            'conflicts': []
        }


def generate_payment_audit_pdf(payment_data, audit_trail):
    """
    Generate a PDF audit report for a payment
    
    Args:
        payment_data (dict): Dictionary containing payment information
        audit_trail (list): List of audit trail entries
        
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
    
    # Title
    elements.append(Paragraph("CINEMA POS", title_style))
    elements.append(Paragraph("PAYMENT AUDIT REPORT", title_style))
    elements.append(Spacer(1, 20))
    
    # Payment summary
    elements.append(Paragraph("Payment Summary", heading_style))
    
    summary_details = [
        ["Payment ID:", f"#{payment_data.get('id', 'N/A')}"],
        ["Booking ID:", f"#{payment_data.get('booking_id', 'N/A')}"],
        ["Customer:", payment_data.get('customer_name', 'N/A')],
        ["Amount:", f"₹{payment_data.get('amount', '0.00')}"],
        ["Payment Method:", payment_data.get('payment_method', 'N/A')],
        ["Status:", payment_data.get('status', 'N/A')],
        ["Created Date:", payment_data.get('created_at', datetime.now()).strftime('%d %b %Y %H:%M')],
    ]
    
    summary_table = Table(summary_details, colWidths=[2*inch, 4*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Audit trail
    elements.append(Paragraph("Audit Trail", heading_style))
    
    if audit_trail:
        audit_headers = ['Timestamp', 'Operation', 'User', 'IP Address', 'Changes']
        audit_data = [audit_headers]
        
        for audit in audit_trail:
            row = [
                audit.get('timestamp', 'N/A'),
                audit.get('operation', 'N/A'),
                f"User {audit.get('user_id', 'N/A')}" if audit.get('user_id') else 'System',
                audit.get('ip_address', 'N/A'),
                ', '.join([f"{k}: {v}" for k, v in audit.get('changes', {}).items()])
            ]
            audit_data.append(row)
        
        audit_table = Table(audit_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch, 3*inch])
        audit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        
        elements.append(audit_table)
    else:
        elements.append(Paragraph("No audit trail data available", normal_style))
    
    elements.append(Spacer(1, 30))
    
    # Footer
    elements.append(Paragraph(f"Report generated on: {datetime.now().strftime('%d %b %Y %H:%M')}", normal_style))
    elements.append(Paragraph("This is a computer-generated audit report.", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data