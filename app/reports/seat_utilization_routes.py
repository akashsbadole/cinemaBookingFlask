"""
Seat Utilization Report Routes
"""
from flask import render_template, redirect, url_for, flash, request, make_response, jsonify
from flask_login import login_required
from app.reports import bp
from app.auth.decorators import admin_required
from app.screens.utils import get_seat_utilization_data, get_seat_type_performance
from app.screens.forms import SeatUtilizationForm
from app.utils import generate_report_pdf
from datetime import datetime, timedelta

@bp.route('/seat_utilization')
@login_required
@admin_required
def seat_utilization():
    """Seat utilization report"""
    form = SeatUtilizationForm()
    
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    screen_id = request.args.get('screen')
    
    # Default to last 30 days if no dates provided
    if not start_date_str:
        start_date = datetime.now() - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.now() - timedelta(days=30)
    
    if not end_date_str:
        end_date = datetime.now().date()
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = datetime.now().date()
    
    # Convert screen_id to integer if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    
    # Get seat utilization data
    utilization_data = get_seat_utilization_data(start_date, end_date, screen_id)
    
    # Get seat type performance data
    seat_type_data = get_seat_type_performance(start_date, end_date, screen_id)
    
    # Calculate totals
    total_seats = sum([row.total_seats for row in utilization_data])
    total_booked = sum([row.booked_seats for row in utilization_data])
    total_available = total_seats - total_booked
    overall_utilization = (total_booked / total_seats * 100) if total_seats > 0 else 0
    
    # Prepare data for charts
    screen_names = [row.screen_name for row in utilization_data]
    utilization_rates = [row.utilization_rate for row in utilization_data]
    
    # Seat type chart data
    seat_types = [row.seat_type for row in seat_type_data]
    seat_type_counts = [row.total_seats for row in seat_type_data]
    seat_type_bookings = [row.booked_seats for row in seat_type_data]
    
    # Set form values
    form.start_date.data = start_date
    form.end_date.data = end_date
    
    # Set screen_id if provided and form has the field
    if hasattr(form, 'screen_id'):
        form.screen_id.data = screen_id or 0
    
    # Get all screens for dropdown
    from app.screens.models import Screen
    all_screens = Screen.query.all()
    
    return render_template(
        'reports/seat_utilization.html',
        title='Seat Utilization Report',
        form=form,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        utilization_data=utilization_data,
        seat_type_data=seat_type_data,
        total_seats=total_seats,
        total_booked=total_booked,
        total_available=total_available,
        overall_utilization=overall_utilization,
        screen_names=screen_names,
        utilization_rates=utilization_rates,
        seat_types=seat_types,
        seat_type_counts=seat_type_counts,
        seat_type_bookings=seat_type_bookings,
        screens=all_screens
    )

@bp.route('/seat_utilization/pdf')
@login_required
@admin_required
def seat_utilization_pdf():
    """Generate PDF seat utilization report"""
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    screen_id = request.args.get('screen')
    
    # Default to last 30 days if no dates provided
    if not start_date_str:
        start_date = datetime.now() - timedelta(days=30)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.now() - timedelta(days=30)
    
    if not end_date_str:
        end_date = datetime.now().date()
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = datetime.now().date()
    
    # Convert screen_id to integer if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    
    # Get seat utilization data
    utilization_data = get_seat_utilization_data(start_date, end_date, screen_id)
    
    # Get seat type performance data
    seat_type_data = get_seat_type_performance(start_date, end_date, screen_id)
    
    # Calculate totals
    total_seats = sum([row.total_seats for row in utilization_data])
    total_booked = sum([row.booked_seats for row in utilization_data])
    overall_utilization = (total_booked / total_seats * 100) if total_seats > 0 else 0
    
    # Prepare report data
    report_data = {
        'summary': {
            'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
            'Total Seats': total_seats,
            'Total Booked': total_booked,
            'Overall Utilization': f"{overall_utilization:.1f}%"
        },
        'data': []
    }
    
    # Add utilization data
    for row in utilization_data:
        report_data['data'].append({
            'screen_name': row.screen_name,
            'total_seats': row.total_seats,
            'booked_seats': row.booked_seats,
            'available_seats': row.available_seats,
            'utilization_rate': f"{row.utilization_rate:.1f}%"
        })
    
    # Add seat type data
    for row in seat_type_data:
        report_data['data'].append({
            'seat_type': row.seat_type,
            'total_seats': row.total_seats,
            'booked_seats': row.booked_seats,
            'utilization_rate': f"{(row.booked_seats / row.total_seats * 100):.1f}%" if row.total_seats > 0 else "0%"
        })
    
    # Generate PDF using utility
    pdf_data = generate_report_pdf(report_data, 'seat_utilization')
    
    # Create response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=seat_utilization_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.pdf'
    
    return response