"""
Reports Utilities
"""
import io
import csv
import pandas as pd
from flask import make_response
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime

def generate_report_pdf(report_data, report_type):
    """Generate PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Build story
    story = []
    
    # Add title
    if report_type == 'daily_sales':
        title = f"Daily Sales Report - {report_data['summary'].get('Report Date', 'N/A')}"
    elif report_type == 'occupancy':
        title = f"Occupancy Report - {report_data['summary'].get('Period', 'N/A')}"
    elif report_type == 'cashier_summary':
        title = f"Cashier Summary - {report_data['summary'].get('Period', 'N/A')}"
    else:
        title = f"{report_type.replace('_', ' ').title()} Report"
    
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    
    # Add summary section
    if 'summary' in report_data:
        story.append(Paragraph("Summary", styles['Heading2']))
        summary_data = []
        for key, value in report_data['summary'].items():
            summary_data.append([key.replace('_', ' ').title(), str(value)])
        
        summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
    
    # Add detailed data section
    if 'data' in report_data and report_data['data']:
        story.append(Paragraph("Detailed Data", styles['Heading2']))
        
        # Create headers based on first data item
        if report_data['data']:
            headers = list(report_data['data'][0].keys())
            data_rows = []
            
            # Add headers
            data_rows.append([h.replace('_', ' ').title() for h in headers])
            
            # Add data rows
            for item in report_data['data']:
                row = []
                for header in headers:
                    value = item.get(header, '')
                    if isinstance(value, float):
                        if header in ['revenue', 'amount', 'average_transaction']:
                            row.append(f"₹{value:.2f}")
                        else:
                            row.append(f"{value:.2f}")
                    else:
                        row.append(str(value))
                data_rows.append(row)
            
            # Create table
            data_table = Table(data_rows, colWidths=[1.5*inch] * len(headers))
            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8)
            ]))
            story.append(data_table)
    
    # Build PDF
    doc.build(story)
    
    # Get PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

def generate_report_excel(report_data, report_type):
    """Generate Excel report"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        if 'summary' in report_data:
            summary_df = pd.DataFrame(
                list(report_data['summary'].items()),
                columns=['Metric', 'Value']
            )
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Data sheet
        if 'data' in report_data and report_data['data']:
            data_df = pd.DataFrame(report_data['data'])
            data_df.to_excel(writer, sheet_name='Data', index=False)
    
    output.seek(0)
    return output.getvalue()

def generate_report_csv(report_data, report_type):
    """Generate CSV report"""
    output = io.StringIO()
    
    if 'data' in report_data and report_data['data']:
        writer = csv.DictWriter(output, fieldnames=report_data['data'][0].keys())
        writer.writeheader()
        writer.writerows(report_data['data'])
    
    return output.getvalue()

def create_download_response(data, filename, content_type):
    """Create download response"""
    response = make_response(data)
    response.headers['Content-Type'] = content_type
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

def export_report(report_data, report_type, export_format='pdf'):
    """Export report in specified format"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if export_format == 'pdf':
        data = generate_report_pdf(report_data, report_type)
        filename = f"{report_type}_{timestamp}.pdf"
        content_type = 'application/pdf'
    elif export_format == 'excel':
        data = generate_report_excel(report_data, report_type)
        filename = f"{report_type}_{timestamp}.xlsx"
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif export_format == 'csv':
        data = generate_report_csv(report_data, report_type)
        filename = f"{report_type}_{timestamp}.csv"
        content_type = 'text/csv'
    else:
        raise ValueError(f"Unsupported export format: {export_format}")
    
    return create_download_response(data, filename, content_type)

def calculate_business_metrics(data):
    """Calculate business metrics from report data"""
    metrics = {}
    
    if 'data' in data and data['data']:
        # Calculate average values
        total_revenue = sum(item.get('revenue', 0) for item in data['data'])
        total_bookings = len(data['data'])
        total_tickets = sum(item.get('tickets_sold', 0) for item in data['data'])
        total_seats = sum(item.get('total_seats', 0) for item in data['data'])
        
        metrics['average_revenue_per_booking'] = total_revenue / total_bookings if total_bookings > 0 else 0
        metrics['average_tickets_per_booking'] = total_tickets / total_bookings if total_bookings > 0 else 0
        metrics['overall_occupancy_rate'] = (total_tickets / total_seats * 100) if total_seats > 0 else 0
        metrics['revenue_per_ticket'] = total_revenue / total_tickets if total_tickets > 0 else 0
        
        # Find best and worst performers
        if 'revenue' in data['data'][0]:
            revenue_sorted = sorted(data['data'], key=lambda x: x.get('revenue', 0), reverse=True)
            metrics['best_performer'] = revenue_sorted[0] if revenue_sorted else None
            metrics['worst_performer'] = revenue_sorted[-1] if revenue_sorted else None
        
        if 'occupancy_rate' in data['data'][0]:
            occupancy_sorted = sorted(data['data'], key=lambda x: x.get('occupancy_rate', 0), reverse=True)
            metrics['highest_occupancy'] = occupancy_sorted[0] if occupancy_sorted else None
            metrics['lowest_occupancy'] = occupancy_sorted[-1] if occupancy_sorted else None
    
    return metrics

def generate_insights(data, report_type):
    """Generate business insights based on report data"""
    insights = []
    
    if not data or 'data' not in data or not data['data']:
        return insights
    
    if report_type == 'daily_sales':
        # Sales insights
        total_revenue = sum(item.get('revenue', 0) for item in data['data'])
        avg_revenue = total_revenue / len(data['data']) if data['data'] else 0
        
        # Peak performing time
        if 'revenue' in data['data'][0]:
            peak_show = max(data['data'], key=lambda x: x.get('revenue', 0))
            if peak_show:
                insights.append({
                    'type': 'success',
                    'message': f"Peak performance: {peak_show.get('movie_title', 'N/A')} at {peak_show.get('show_time', 'N/A')} with ₹{peak_show.get('revenue', 0):.2f}"
                })
        
        # Low performing shows
        if 'revenue' in data['data'][0]:
            low_shows = [item for item in data['data'] if item.get('revenue', 0) < avg_revenue * 0.5]
            if low_shows:
                insights.append({
                    'type': 'warning',
                    'message': f"Consider promoting or rescheduling shows with low revenue: {', '.join([s.get('movie_title', 'N/A') for s in low_shows[:3]])}"
                })
    
    elif report_type == 'occupancy':
        # Occupancy insights
        avg_occupancy = sum(item.get('occupancy_rate', 0) for item in data['data']) / len(data['data']) if data['data'] else 0
        
        if avg_occupancy < 60:
            insights.append({
                'type': 'warning',
                'message': "Overall occupancy is below 60%. Consider adjusting pricing or show timing."
            })
        elif avg_occupancy > 85:
            insights.append({
                'type': 'success',
                'message': "Excellent occupancy! Consider adding more shows during peak times."
            })
        
        # Peak times analysis
        if 'show_time' in data['data'][0]:
            time_analysis = {}
            for item in data['data']:
                hour = item.get('show_time', datetime.now()).hour if hasattr(item.get('show_time', datetime.now()), 'hour') else 12
                if hour not in time_analysis:
                    time_analysis[hour] = []
                time_analysis[hour].append(item.get('occupancy_rate', 0))
            
            peak_hour = max(time_analysis.keys(), key=lambda h: sum(time_analysis[h]) / len(time_analysis[h])) if time_analysis else 12
            if peak_hour and time_analysis[peak_hour]:
                avg_occupancy_at_peak = sum(time_analysis[peak_hour]) / len(time_analysis[peak_hour])
                if avg_occupancy_at_peak > 80:
                    insights.append({
                        'type': 'info',
                        'message': f"Peak occupancy occurs at {peak_hour}:00 with {avg_occupancy_at_peak:.1f}% average"
                    })
    
    elif report_type == 'cashier_summary':
        # Cashier performance insights
        if 'performance_score' in data['data'][0]:
            top_performers = sorted(data['data'], key=lambda x: x.get('performance_score', 0), reverse=True)[:3]
            low_performers = sorted(data['data'], key=lambda x: x.get('performance_score', 0))[:3]
            
            if top_performers:
                insights.append({
                    'type': 'success',
                    'message': f"Top performers: {', '.join([p.get('username', 'N/A') for p in top_performers])}"
                })
            
            if low_performers:
                insights.append({
                    'type': 'warning',
                    'message': f"Consider additional training for: {', '.join([p.get('username', 'N/A') for p in low_performers])}"
                })
    
    return insights