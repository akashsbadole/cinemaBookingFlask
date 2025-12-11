"""
Reports Routes
"""
from flask import render_template, redirect, url_for, flash, request, make_response, jsonify
from flask_login import login_required
from app.reports import bp
from app.reports.forms import (
    DailySalesForm, OccupancyForm, CashierSummaryForm,
    MoviePerformanceForm, ScreenUtilizationForm, ExportForm, ReportTypeForm
)
from app.reports.models import ReportQueries
from app.reports.utils import export_report, calculate_business_metrics, generate_insights
from app.auth.decorators import admin_required
from app.shows.models import Show
from app.screens.models import Screen, Seat
from app.auth.models import User
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.movies.models import Movie
from app.database import db
from app.utils import generate_report_pdf
from datetime import datetime, timedelta
from sqlalchemy import func, and_

@bp.route('/')
@login_required
@admin_required
def index():
    """Reports dashboard"""
    # Get today's summary for dashboard
    today = datetime.now().date()
    
    # Quick stats
    today_sales = db.session.query(func.sum(Payment.amount)).join(Booking).join(Show).filter(
        Show.show_date == today
    ).scalar() or 0
    
    today_bookings = db.session.query(func.count(Booking.id)).join(Show).filter(
        Show.show_date == today
    ).scalar() or 0
    
    today_tickets = db.session.query(func.count(BookingSeat.id)).join(Booking).join(Show).filter(
        Show.show_date == today
    ).scalar() or 0
    
    # Calculate average tickets per booking
    avg_tickets = today_tickets / today_bookings if today_bookings > 0 else 0
    
    # Get recent activity
    recent_activity = db.session.query(
        Booking.booking_time,
        Show.show_time,
        Movie.title,
        Screen.name,
        func.count(BookingSeat.id).label('seats'),
        Payment.amount,
        User.username
    ).join(
        BookingSeat, Booking.id == BookingSeat.booking_id
    ).join(
        Show, Booking.show_id == Show.id
    ).join(
        Movie, Show.movie_id == Movie.id
    ).join(
        Screen, Show.screen_id == Screen.id
    ).join(
        Payment, Booking.id == Payment.booking_id
    ).join(
        User, Booking.user_id == User.id
    ).filter(
        Show.show_date == today
    ).group_by(
        Booking.id, Show.show_time, Movie.title, Screen.name, Payment.amount, User.username
    ).order_by(
        Booking.booking_time.desc()
    ).limit(5).all()
    
    return render_template(
        'reports/index.html',
        title='Reports',
        today_sales=today_sales,
        today_bookings=today_bookings,
        today_tickets=today_tickets,
        avg_tickets=avg_tickets,
        recent_activity=recent_activity
    )

@bp.route('/daily_sales')
@login_required
@admin_required
def daily_sales():
    """Daily sales report"""
    form = DailySalesForm()
    
    # Get filter parameters
    report_date_str = request.args.get('date')
    screen_id = request.args.get('screen')
    movie_id = request.args.get('movie')
    
    # Default to today if no date provided
    if not report_date_str:
        report_date = datetime.now().date()
    else:
        try:
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
        except ValueError:
            report_date = datetime.now().date()
    
    # Convert IDs to integers if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    movie_id = int(movie_id) if movie_id and movie_id != '0' else None
    
    # Get sales data using ReportQueries
    sales_data = ReportQueries.get_daily_sales_data(report_date, screen_id, movie_id)
    
    # Get movie and screen breakdowns
    movie_sales = ReportQueries.get_movie_sales_breakdown(report_date, screen_id, movie_id)
    screen_sales = ReportQueries.get_screen_sales_breakdown(report_date, screen_id, movie_id)
    
    # Calculate totals
    total_sales = sum([row.revenue or 0 for row in sales_data])
    total_bookings = sum([row.bookings_count or 0 for row in sales_data])
    tickets_sold = sum([row.tickets_sold or 0 for row in sales_data])
    average_sale = total_sales / total_bookings if total_bookings > 0 else 0
    
    # Calculate occupancy rate
    total_seats = db.session.query(func.count(Seat.id)).join(Screen).scalar() or 0
    occupancy_rate = (tickets_sold / total_seats * 100) if total_seats > 0 else 0
    
    # Calculate occupancy rate for each show
    for sale in sales_data:
        show_total_seats = db.session.query(func.count(Seat.id)).join(Screen).filter(
            Screen.name == sale.screen_name
        ).scalar() or 0
        sale.occupancy_rate = (sale.tickets_sold / show_total_seats * 100) if show_total_seats > 0 else 0
    
    # Prepare data for charts
    movie_sales_labels = [row.title for row in movie_sales]
    movie_sales_data = [float(row.revenue or 0) for row in movie_sales]
    
    screen_sales_labels = [row.name for row in screen_sales]
    screen_sales_data = [float(row.revenue or 0) for row in screen_sales]
    
    # Generate business insights
    report_data = {
        'data': [{
            'movie_title': sale.movie_title,
            'screen_name': sale.screen_name,
            'show_time': sale.show_time.strftime('%H:%M'),
            'tickets_sold': sale.tickets_sold,
            'revenue': float(sale.revenue or 0),
            'occupancy_rate': sale.occupancy_rate
        } for sale in sales_data]
    }
    
    insights = generate_insights(report_data, 'daily_sales')
    
    # Set form values
    form.report_date.data = report_date
    form.screen_id.data = screen_id or 0
    form.movie_id.data = movie_id or 0
    
    return render_template(
        'reports/daily_sales.html',
        title='Daily Sales Report',
        form=form,
        report_date=report_date.strftime('%Y-%m-%d'),
        sales_data=sales_data,
        total_sales=total_sales,
        total_bookings=total_bookings,
        average_sale=average_sale,
        tickets_sold=tickets_sold,
        occupancy_rate=occupancy_rate,
        movie_sales_labels=movie_sales_labels,
        movie_sales_data=movie_sales_data,
        screen_sales_labels=screen_sales_labels,
        screen_sales_data=screen_sales_data,
        insights=insights
    )

@bp.route('/daily_sales/pdf')
@login_required
@admin_required
def daily_sales_pdf():
    """Generate PDF daily sales report"""
    # Get filter parameters
    report_date_str = request.args.get('date')
    screen_id = request.args.get('screen')
    movie_id = request.args.get('movie')
    
    # Default to today if no date provided
    if not report_date_str:
        report_date = datetime.now().date()
    else:
        try:
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
        except ValueError:
            report_date = datetime.now().date()
    
    # Convert IDs to integers if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    movie_id = int(movie_id) if movie_id and movie_id != '0' else None
    
    # Get sales data using ReportQueries
    sales_data = ReportQueries.get_daily_sales_data(report_date, screen_id, movie_id)
    
    # Calculate totals
    total_sales = sum([row.revenue or 0 for row in sales_data])
    total_bookings = sum([row.bookings_count or 0 for row in sales_data])
    tickets_sold = sum([row.tickets_sold or 0 for row in sales_data])
    average_sale = total_sales / total_bookings if total_bookings > 0 else 0
    
    # Prepare report data
    report_data = {
        'summary': {
            'Total Sales': f"₹{total_sales:.2f}",
            'Total Bookings': total_bookings,
            'Average Sale': f"₹{average_sale:.2f}",
            'Tickets Sold': tickets_sold,
            'Report Date': report_date.strftime('%d %b %Y')
        },
        'data': []
    }
    
    # Add sales data
    for row in sales_data:
        report_data['data'].append({
            'time': row.show_time.strftime('%H:%M'),
            'movie_title': row.movie_title,
            'screen_name': row.screen_name,
            'show_date': row.show_date.strftime('%d %b %Y'),
            'bookings_count': row.bookings_count,
            'tickets_sold': row.tickets_sold,
            'revenue': float(row.revenue or 0)
        })
    
    # Generate PDF using utility
    pdf_data = generate_report_pdf(report_data, 'daily_sales')
    
    # Create response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=daily_sales_{report_date.strftime("%Y%m%d")}.pdf'
    
    return response

@bp.route('/occupancy')
@login_required
@admin_required
def occupancy():
    """Seat occupancy report"""
    form = OccupancyForm()
    
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    screen_id = request.args.get('screen')
    movie_id = request.args.get('movie')
    
    # Default to last 7 days if no dates provided
    if not start_date_str:
        start_date = datetime.now() - timedelta(days=7)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.now() - timedelta(days=7)
    
    if not end_date_str:
        end_date = datetime.now().date()
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = datetime.now().date()
    
    # Convert IDs to integers if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    movie_id = int(movie_id) if movie_id and movie_id != '0' else None
    
    # Get occupancy data using ReportQueries
    occupancy_data = ReportQueries.get_occupancy_data(start_date, end_date, screen_id, movie_id)
    
    # Calculate occupancy rate for each show
    for data in occupancy_data:
        data.occupancy_rate = (data.seats_sold / data.total_seats * 100) if data.total_seats > 0 else 0
    
    # Calculate overall metrics
    total_seats = sum([row.total_seats or 0 for row in occupancy_data])
    total_seats_sold = sum([row.seats_sold or 0 for row in occupancy_data])
    overall_occupancy = (total_seats_sold / total_seats * 100) if total_seats > 0 else 0
    
    # Get peak occupancy times
    peak_data = ReportQueries.get_peak_occupancy_times(start_date, end_date)
    
    # Find peak day
    peak_day_data = max(peak_data['peak_days'], key=lambda x: (x.seats_sold / x.total_seats * 100) if x.total_seats > 0 else 0) if peak_data['peak_days'] else None
    peak_day = peak_day_data.show_date.strftime('%d %b %Y') if peak_day_data else 'N/A'
    peak_occupancy = (peak_day_data.seats_sold / peak_day_data.total_seats * 100) if peak_day_data and peak_day_data.total_seats > 0 else 0
    
    # Find peak time
    peak_time_data = max(peak_data['peak_times'], key=lambda x: (x.seats_sold / x.total_seats * 100) if x.total_seats > 0 else 0) if peak_data['peak_times'] else None
    peak_time = f"{int(peak_time_data.hour):02d}:00" if peak_time_data else 'N/A'
    peak_time_occupancy = (peak_time_data.seats_sold / peak_time_data.total_seats * 100) if peak_time_data and peak_time_data.total_seats > 0 else 0
    
    # Calculate revenue impact (assuming average ticket price of ₹200)
    total_revenue = sum([row.revenue or 0 for row in occupancy_data])
    revenue_impact = (total_seats * 200) - total_revenue
    
    # Get trend data for charts
    trend_data = {}
    for data in occupancy_data:
        date_str = data.show_date.strftime('%Y-%m-%d')
        if date_str not in trend_data:
            trend_data[date_str] = {'seats_sold': 0, 'total_seats': 0}
        trend_data[date_str]['seats_sold'] += data.seats_sold or 0
        trend_data[date_str]['total_seats'] += data.total_seats or 0
    
    trend_labels = sorted(trend_data.keys())
    trend_data_list = []
    for label in trend_labels:
        occupancy = (trend_data[label]['seats_sold'] / trend_data[label]['total_seats'] * 100) if trend_data[label]['total_seats'] > 0 else 0
        trend_data_list.append(round(occupancy, 1))
    
    # Screen performance for pie chart
    screen_performance = {}
    for data in occupancy_data:
        if data.screen_name not in screen_performance:
            screen_performance[data.screen_name] = {'revenue': 0, 'seats_sold': 0}
        screen_performance[data.screen_name]['revenue'] += data.revenue or 0
        screen_performance[data.screen_name]['seats_sold'] += data.seats_sold or 0
    
    screen_perf_labels = list(screen_performance.keys())
    screen_perf_data = [float(screen_perf[label]['revenue']) for label in screen_perf_labels]
    
    # Set form values
    form.start_date.data = start_date
    form.end_date.data = end_date
    form.screen_id.data = screen_id or 0
    form.movie_id.data = movie_id or 0
    
    return render_template(
        'reports/occupancy.html',
        title='Occupancy Report',
        form=form,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        occupancy_data=occupancy_data,
        overall_occupancy=overall_occupancy,
        total_seats=total_seats,
        total_seats_sold=total_seats_sold,
        peak_day=peak_day,
        peak_occupancy=peak_occupancy,
        peak_time=peak_time,
        peak_time_occupancy=peak_time_occupancy,
        revenue_impact=revenue_impact,
        trend_labels=trend_labels,
        trend_data=trend_data_list,
        screen_performance_labels=screen_perf_labels,
        screen_performance_data=screen_perf_data,
        low_performing_shows=[row for row in occupancy_data if row.occupancy_rate < 40][:5],
        high_performing_shows=[row for row in occupancy_data if row.occupancy_rate >= 80][:5]
    )

@bp.route('/occupancy/pdf')
@login_required
@admin_required
def occupancy_pdf():
    """Generate PDF occupancy report"""
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    screen_id = request.args.get('screen')
    
    # Default to last 7 days if no dates provided
    if not start_date_str:
        start_date = datetime.now() - timedelta(days=7)
    else:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.now() - timedelta(days=7)
    
    if not end_date_str:
        end_date = datetime.now().date()
    else:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = datetime.now().date()
    
    # Convert IDs to integers if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    
    # Get occupancy data using ReportQueries
    occupancy_data = ReportQueries.get_occupancy_data(start_date, end_date, screen_id)
    
    # Calculate overall metrics
    total_seats = sum([row.total_seats or 0 for row in occupancy_data])
    total_seats_sold = sum([row.seats_sold or 0 for row in occupancy_data])
    overall_occupancy = (total_seats_sold / total_seats * 100) if total_seats > 0 else 0
    
    # Prepare report data
    report_data = {
        'summary': {
            'Overall Occupancy': f"{overall_occupancy:.1f}%",
            'Total Seats': total_seats,
            'Seats Sold': total_seats_sold,
            'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        },
        'data': []
    }
    
    # Add occupancy data
    for row in occupancy_data:
        occupancy_rate = (row.seats_sold / row.total_seats * 100) if row.total_seats > 0 else 0
        report_data['data'].append({
            'date': row.show_date.strftime('%d %b %Y'),
            'movie_title': row.movie_title,
            'screen_name': row.screen_name,
            'show_time': row.show_time.strftime('%H:%M'),
            'total_seats': row.total_seats,
            'seats_sold': row.seats_sold,
            'occupancy_rate': occupancy_rate,
            'revenue': float(row.revenue or 0)
        })
    
    # Generate PDF using utility
    pdf_data = generate_report_pdf(report_data, 'occupancy')
    
    # Create response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=occupancy_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.pdf'
    
    return response

@bp.route('/cashier_summary')
@login_required
@admin_required
def cashier_summary():
    """Cashier performance summary"""
    form = CashierSummaryForm()
    
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    cashier_id = request.args.get('cashier')
    
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
    
    # Convert IDs to integers if provided
    cashier_id = int(cashier_id) if cashier_id and cashier_id != '0' else None
    
    # Get cashier performance data using ReportQueries
    cashier_data = ReportQueries.get_cashier_performance_data(start_date, end_date, cashier_id)
    
    # Calculate totals
    total_revenue = sum([row.revenue or 0 for row in cashier_data])
    total_bookings = sum([row.bookings_count or 0 for row in cashier_data])
    total_tickets = sum([row.tickets_sold or 0 for row in cashier_data])
    average_transaction = total_revenue / total_bookings if total_bookings > 0 else 0
    
    # Find top performer
    top_performer = max(cashier_data, key=lambda x: x.revenue or 0) if cashier_data else None
    top_performer_name = top_performer.username if top_performer else 'N/A'
    top_performer_revenue = float(top_performer.revenue or 0) if top_performer else 0
    
    # Calculate performance score for each cashier
    for cashier in cashier_data:
        # Calculate performance score based on revenue and number of bookings
        revenue_score = min(100, (cashier.revenue / 10000) * 100) if cashier.revenue else 0  # Assuming ₹10,000 as target
        booking_score = min(100, (cashier.bookings_count / 50) * 100) if cashier.bookings_count else 0  # Assuming 50 bookings as target
        cashier.performance_score = (revenue_score + booking_score) / 2
        
        # Calculate refunds (simplified - in real implementation, would need refund data)
        cashier.refunds_count = 0  # Placeholder
        cashier.net_revenue = cashier.revenue  # Placeholder
        cashier.tickets_sold = cashier.tickets_sold or 0
    
    # Sort cashiers by performance score
    cashier_data_sorted = sorted(cashier_data, key=lambda x: x.performance_score or 0, reverse=True)
    
    # Prepare data for charts
    cashier_names = [c.username for c in cashier_data_sorted]
    cashier_revenues = [float(c.revenue or 0) for c in cashier_data_sorted]
    cashier_net_revenues = [float(c.net_revenue or 0) for c in cashier_data_sorted]
    
    # Get top performers for rankings
    top_revenue_performers = sorted(cashier_data, key=lambda x: x.revenue or 0, reverse=True)[:5]
    top_booking_performers = sorted(cashier_data, key=lambda x: x.bookings_count or 0, reverse=True)[:5]
    top_satisfaction_performers = sorted(cashier_data, key=lambda x: x.performance_score or 0, reverse=True)[:5]
    
    # Set form values
    form.start_date.data = start_date
    form.end_date.data = end_date
    form.cashier_id.data = cashier_id or 0
    
    return render_template(
        'reports/cashier_summary.html',
        title='Cashier Summary',
        form=form,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        cashier_data=cashier_data_sorted,
        total_revenue=total_revenue,
        total_bookings=total_bookings,
        total_tickets=total_tickets,
        average_transaction=average_transaction,
        top_performer=top_performer_name,
        top_performer_revenue=top_performer_revenue,
        cashier_names=cashier_names,
        cashier_revenues=cashier_revenues,
        cashier_net_revenues=cashier_net_revenues,
        top_revenue_performers=top_revenue_performers,
        top_booking_performers=top_booking_performers,
        top_satisfaction_performers=top_satisfaction_performers
    )

@bp.route('/cashier_summary/pdf')
@login_required
@admin_required
def cashier_summary_pdf():
    """Generate PDF cashier summary report"""
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    cashier_id = request.args.get('cashier')
    
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
    
    # Convert IDs to integers if provided
    cashier_id = int(cashier_id) if cashier_id and cashier_id != '0' else None
    
    # Get cashier performance data using ReportQueries
    cashier_data = ReportQueries.get_cashier_performance_data(start_date, end_date, cashier_id)
    
    # Calculate totals
    total_revenue = sum([row.revenue or 0 for row in cashier_data])
    total_bookings = sum([row.bookings_count or 0 for row in cashier_data])
    average_transaction = total_revenue / total_bookings if total_bookings > 0 else 0
    
    # Prepare report data
    report_data = {
        'summary': {
            'Total Revenue': f"₹{total_revenue:.2f}",
            'Total Bookings': total_bookings,
            'Average Transaction': f"₹{average_transaction:.2f}",
            'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        },
        'data': []
    }
    
    # Add cashier data
    for row in cashier_data:
        # Calculate performance score (simplified)
        performance_score = min(100, (row.revenue / 10000) * 100) if row.revenue else 0  # Assuming ₹10,000 as target
        
        report_data['data'].append({
            'username': row.username,
            'bookings_count': row.bookings_count,
            'tickets_sold': row.tickets_sold or 0,
            'revenue': float(row.revenue or 0),
            'average_transaction': float(row.average_transaction or 0),
            'performance_score': performance_score
        })
    
    # Generate PDF using utility
    pdf_data = generate_report_pdf(report_data, 'cashier_summary')
    
    # Create response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=cashier_summary_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.pdf'
    
    return response

@bp.route('/movie_performance')
@login_required
@admin_required
def movie_performance():
    """Movie performance report"""
    form = MoviePerformanceForm()
    
    # Get filter parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    movie_id = request.args.get('movie')
    
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
    
    # Convert IDs to integers if provided
    movie_id = int(movie_id) if movie_id and movie_id != '0' else None
    
    # Get movie performance data using ReportQueries
    movie_data = ReportQueries.get_movie_performance_data(start_date, end_date, movie_id)
    
    # Calculate average occupancy for each movie
    for movie in movie_data:
        # Get total seats for this movie
        total_seats = db.session.query(func.count(Seat.id)).join(Screen).join(Show).filter(
            Show.movie_id == movie.id
        ).scalar() or 0
        movie.occupancy_rate = (movie.tickets_sold / total_seats * 100) if total_seats > 0 else 0
        movie.revenue_per_show = movie.revenue / movie.days_running if movie.days_running > 0 else 0
    
    # Sort by revenue
    movie_data_sorted = sorted(movie_data, key=lambda x: x.revenue or 0, reverse=True)
    
    # Calculate totals
    total_revenue = sum([movie.revenue or 0 for movie in movie_data])
    total_bookings = sum([movie.bookings_count or 0 for movie in movie_data])
    total_tickets = sum([movie.tickets_sold or 0 for movie in movie_data])
    
    # Prepare data for charts
    movie_names = [m.title for m in movie_data_sorted[:10]]  # Top 10 movies
    movie_revenues = [float(m.revenue or 0) for m in movie_data_sorted[:10]]
    movie_occupancies = [float(m.occupancy_rate) for m in movie_data_sorted[:10]]
    
    # Set form values
    form.start_date.data = start_date
    form.end_date.data = end_date
    form.movie_id.data = movie_id or 0
    
    return render_template(
        'reports/movie_performance.html',
        title='Movie Performance Report',
        form=form,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        movie_data=movie_data_sorted,
        total_revenue=total_revenue,
        total_bookings=total_bookings,
        total_tickets=total_tickets,
        movie_names=movie_names,
        movie_revenues=movie_revenues,
        movie_occupancies=movie_occupancies
    )

@bp.route('/screen_utilization')
@login_required
@admin_required
def screen_utilization():
    """Screen utilization report"""
    form = ScreenUtilizationForm()
    
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
    
    # Convert IDs to integers if provided
    screen_id = int(screen_id) if screen_id and screen_id != '0' else None
    
    # Get screen utilization data using ReportQueries
    screen_data = ReportQueries.get_screen_utilization_data(start_date, end_date, screen_id)
    
    # Calculate additional metrics
    for screen in screen_data:
        screen.tickets_per_show = screen.total_tickets_sold / screen.total_shows if screen.total_shows > 0 else 0
        screen.revenue_per_show = screen.total_revenue / screen.total_shows if screen.total_shows > 0 else 0
    
    # Sort by utilization
    screen_data_sorted = sorted(screen_data, key=lambda x: x.average_occupancy or 0, reverse=True)
    
    # Calculate totals
    total_shows = sum([screen.total_shows or 0 for screen in screen_data])
    total_bookings = sum([screen.total_bookings or 0 for screen in screen_data])
    total_tickets = sum([screen.total_tickets_sold or 0 for screen in screen_data])
    total_revenue = sum([screen.total_revenue or 0 for screen in screen_data])
    
    # Prepare data for charts
    screen_names = [s.name for s in screen_data_sorted]
    screen_occupancies = [float(s.average_occupancy or 0) for s in screen_data_sorted]
    screen_revenues = [float(s.total_revenue or 0) for s in screen_data_sorted]
    
    # Set form values
    form.start_date.data = start_date
    form.end_date.data = end_date
    form.screen_id.data = screen_id or 0
    
    return render_template(
        'reports/screen_utilization.html',
        title='Screen Utilization Report',
        form=form,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        screen_data=screen_data_sorted,
        total_shows=total_shows,
        total_bookings=total_bookings,
        total_tickets=total_tickets,
        total_revenue=total_revenue,
        screen_names=screen_names,
        screen_occupancies=screen_occupancies,
        screen_revenues=screen_revenues
    )

@bp.route('/export/<report_type>')
@login_required
@admin_required
def export_report_route(report_type):
    """Export report in different formats"""
    export_format = request.args.get('format', 'pdf')
    
    # Get filter parameters based on report type
    if report_type == 'daily_sales':
        report_date_str = request.args.get('date')
        screen_id = request.args.get('screen')
        movie_id = request.args.get('movie')
        
        if not report_date_str:
            report_date = datetime.now().date()
        else:
            try:
                report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
            except ValueError:
                report_date = datetime.now().date()
        
        screen_id = int(screen_id) if screen_id and screen_id != '0' else None
        movie_id = int(movie_id) if movie_id and movie_id != '0' else None
        
        sales_data = ReportQueries.get_daily_sales_data(report_date, screen_id, movie_id)
        
        report_data = {
            'summary': {
                'Report Date': report_date.strftime('%d %b %Y'),
                'Total Sales': f"₹{sum([row.revenue or 0 for row in sales_data]):.2f}",
                'Total Bookings': sum([row.bookings_count or 0 for row in sales_data]),
                'Tickets Sold': sum([row.tickets_sold or 0 for row in sales_data])
            },
            'data': []
        }
        
        for row in sales_data:
            report_data['data'].append({
                'time': row.show_time.strftime('%H:%M'),
                'movie_title': row.movie_title,
                'screen_name': row.screen_name,
                'show_date': row.show_date.strftime('%d %b %Y'),
                'bookings_count': row.bookings_count,
                'tickets_sold': row.tickets_sold,
                'revenue': float(row.revenue or 0)
            })
    
    elif report_type == 'occupancy':
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        screen_id = request.args.get('screen')
        
        if not start_date_str:
            start_date = datetime.now() - timedelta(days=7)
        else:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = datetime.now() - timedelta(days=7)
        
        if not end_date_str:
            end_date = datetime.now().date()
        else:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                end_date = datetime.now().date()
        
        screen_id = int(screen_id) if screen_id and screen_id != '0' else None
        
        occupancy_data = ReportQueries.get_occupancy_data(start_date, end_date, screen_id)
        
        report_data = {
            'summary': {
                'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
                'Total Seats': sum([row.total_seats or 0 for row in occupancy_data]),
                'Seats Sold': sum([row.seats_sold or 0 for row in occupancy_data]),
                'Overall Occupancy': f"{(sum([row.seats_sold or 0 for row in occupancy_data]) / sum([row.total_seats or 0 for row in occupancy_data]) * 100):.1f}%"
            },
            'data': []
        }
        
        for row in occupancy_data:
            occupancy_rate = (row.seats_sold / row.total_seats * 100) if row.total_seats > 0 else 0
            report_data['data'].append({
                'date': row.show_date.strftime('%d %b %Y'),
                'movie_title': row.movie_title,
                'screen_name': row.screen_name,
                'show_time': row.show_time.strftime('%H:%M'),
                'total_seats': row.total_seats,
                'seats_sold': row.seats_sold,
                'occupancy_rate': occupancy_rate,
                'revenue': float(row.revenue or 0)
            })
    
    elif report_type == 'cashier_summary':
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        cashier_id = request.args.get('cashier')
        
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
        
        cashier_id = int(cashier_id) if cashier_id and cashier_id != '0' else None
        
        cashier_data = ReportQueries.get_cashier_performance_data(start_date, end_date, cashier_id)
        
        report_data = {
            'summary': {
                'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
                'Total Revenue': f"₹{sum([row.revenue or 0 for row in cashier_data]):.2f}",
                'Total Bookings': sum([row.bookings_count or 0 for row in cashier_data])
            },
            'data': []
        }
        
        for row in cashier_data:
            performance_score = min(100, (row.revenue / 10000) * 100) if row.revenue else 0
            report_data['data'].append({
                'username': row.username,
                'bookings_count': row.bookings_count,
                'tickets_sold': row.tickets_sold or 0,
                'revenue': float(row.revenue or 0),
                'average_transaction': float(row.average_transaction or 0),
                'performance_score': performance_score
            })
    
    else:
        flash('Invalid report type', 'error')
        return redirect(url_for('reports.index'))
    
    # Export the report
    return export_report(report_data, report_type, export_format)

@bp.route('/payment_methods')
@login_required
@admin_required
def payment_methods():
    """Payment methods breakdown report"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
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
    
    # Get payment method breakdown using ReportQueries
    payment_data = ReportQueries.get_payment_method_breakdown(start_date, end_date)
    payment_status_data = ReportQueries.get_payment_status_breakdown(start_date, end_date)
    
    # Calculate totals
    total_count = sum([row.count for row in payment_data])
    total_amount = sum([row.total_amount for row in payment_data])
    
    # Calculate percentages
    for payment in payment_data:
        payment.percentage = (payment.count / total_count * 100) if total_count > 0 else 0
    
    # Prepare data for charts
    payment_labels = [row.mode.title() for row in payment_data]
    payment_counts = [row.count for row in payment_data]
    payment_amounts = [float(row.total_amount) for row in payment_data]
    
    # Status breakdown data
    status_labels = [row.status.title() for row in payment_status_data]
    status_counts = [row.count for row in payment_status_data]
    status_amounts = [float(row.total_amount) for row in payment_status_data]
    
    return render_template(
        'reports/payment_methods.html',
        title='Payment Methods Report',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        payment_data=payment_data,
        payment_status_data=payment_status_data,
        total_count=total_count,
        total_amount=total_amount,
        payment_labels=payment_labels,
        payment_counts=payment_counts,
        payment_amounts=payment_amounts,
        status_labels=status_labels,
        status_counts=status_counts,
        status_amounts=status_amounts
    )

@bp.route('/payment_analysis')
@login_required
@admin_required
def payment_analysis():
    """Comprehensive payment analysis report"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
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
    
    # Get payment data
    payment_trends = ReportQueries.get_payment_trends(start_date, end_date)
    refund_data = ReportQueries.get_refund_analysis(start_date, end_date)
    failure_data = ReportQueries.get_payment_failure_analysis(start_date, end_date)
    daily_summary = ReportQueries.get_daily_payment_summary(start_date, end_date)
    
    # Calculate totals
    total_transactions = sum([row.total_transactions for row in daily_summary])
    total_amount = sum([row.total_amount for row in daily_summary])
    total_refunds = sum([row.refunded_amount for row in daily_summary])
    total_failures = sum([row.failed_amount for row in daily_summary])
    
    # Calculate success rate
    success_rate = ((total_amount - total_failures) / total_amount * 100) if total_amount > 0 else 0
    refund_rate = (total_refunds / total_amount * 100) if total_amount > 0 else 0
    
    # Prepare data for charts
    dates = [row.date.strftime('%Y-%m-%d') for row in daily_summary]
    daily_amounts = [float(row.total_amount) for row in daily_summary]
    daily_refunds = [float(row.refunded_amount) for row in daily_summary]
    daily_failures = [float(row.failed_amount) for row in daily_summary]
    
    return render_template(
        'reports/payment_analysis.html',
        title='Payment Analysis Report',
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        payment_trends=payment_trends,
        refund_data=refund_data,
        failure_data=failure_data,
        daily_summary=daily_summary,
        total_transactions=total_transactions,
        total_amount=total_amount,
        total_refunds=total_refunds,
        total_failures=total_failures,
        success_rate=success_rate,
        refund_rate=refund_rate,
        dates=dates,
        daily_amounts=daily_amounts,
        daily_refunds=daily_refunds,
        daily_failures=daily_failures
    )

@bp.route('/payment_analysis/pdf')
@login_required
@admin_required
def payment_analysis_pdf():
    """Generate PDF payment analysis report"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
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
    
    # Get payment data
    payment_trends = ReportQueries.get_payment_trends(start_date, end_date)
    refund_data = ReportQueries.get_refund_analysis(start_date, end_date)
    failure_data = ReportQueries.get_payment_failure_analysis(start_date, end_date)
    daily_summary = ReportQueries.get_daily_payment_summary(start_date, end_date)
    
    # Calculate totals
    total_transactions = sum([row.total_transactions for row in daily_summary])
    total_amount = sum([row.total_amount for row in daily_summary])
    total_refunds = sum([row.refunded_amount for row in daily_summary])
    total_failures = sum([row.failed_amount for row in daily_summary])
    
    # Calculate success rate
    success_rate = ((total_amount - total_failures) / total_amount * 100) if total_amount > 0 else 0
    refund_rate = (total_refunds / total_amount * 100) if total_amount > 0 else 0
    
    # Prepare report data
    report_data = {
        'summary': {
            'Period': f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",
            'Total Transactions': total_transactions,
            'Total Amount': f"₹{total_amount:.2f}",
            'Total Refunds': f"₹{total_refunds:.2f}",
            'Total Failures': f"₹{total_failures:.2f}",
            'Success Rate': f"{success_rate:.1f}%",
            'Refund Rate': f"{refund_rate:.1f}%"
        },
        'data': []
    }
    
    # Add daily summary data
    for row in daily_summary:
        report_data['data'].append({
            'date': row.date.strftime('%d %b %Y'),
            'total_transactions': row.total_transactions,
            'total_amount': float(row.total_amount),
            'completed_amount': float(row.completed_amount),
            'failed_amount': float(row.failed_amount),
            'refunded_amount': float(row.refunded_amount)
        })
    
    # Generate PDF using utility
    pdf_data = generate_report_pdf(report_data, 'payment_analysis')
    
    # Create response
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=payment_analysis_{start_date.strftime("%Y%m%d")}_to_{end_date.strftime("%Y%m%d")}.pdf'
    
    return response