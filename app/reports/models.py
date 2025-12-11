"""
Reports Models and Data Queries
"""
from datetime import datetime, timedelta
from sqlalchemy import func, and_, extract
from app import db
from app.shows.models import Show
from app.screens.models import Screen, Seat
from app.auth.models import User
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.movies.models import Movie

class ReportQueries:
    """Class containing all report data queries"""
    
    @staticmethod
    def get_daily_sales_data(report_date, screen_id=None, movie_id=None):
        """Get daily sales data"""
        query = db.session.query(
            Show.show_date,
            Show.show_time,
            Movie.title.label('movie_title'),
            Screen.name.label('screen_name'),
            func.count(Booking.id).label('bookings_count'),
            func.sum(Payment.amount).label('revenue'),
            func.count(BookingSeat.id).label('tickets_sold')
        ).join(
            Booking, Show.id == Booking.show_id
        ).join(
            Payment, Booking.id == Payment.booking_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Movie, Show.movie_id == Movie.id
        ).join(
            Screen, Show.screen_id == Screen.id
        ).filter(
            Show.show_date == report_date
        )
        
        # Apply filters
        if screen_id:
            query = query.filter(Screen.id == screen_id)
        
        if movie_id:
            query = query.filter(Movie.id == movie_id)
        
        # Group by show
        return query.group_by(
            Show.show_date, Show.show_time, Movie.title, Screen.name
        ).all()
    
    @staticmethod
    def get_movie_sales_breakdown(report_date, screen_id=None, movie_id=None):
        """Get sales breakdown by movie"""
        query = db.session.query(
            Movie.title,
            func.sum(Payment.amount).label('revenue'),
            func.count(Booking.id).label('bookings_count'),
            func.count(BookingSeat.id).label('tickets_sold')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Show, Booking.show_id == Show.id
        ).join(
            Movie, Show.movie_id == Movie.id
        ).filter(
            Show.show_date == report_date
        )
        
        # Apply filters
        if screen_id:
            query = query.filter(Screen.id == screen_id)
        
        if movie_id:
            query = query.filter(Movie.id == movie_id)
        
        return query.group_by(Movie.title).all()
    
    @staticmethod
    def get_screen_sales_breakdown(report_date, screen_id=None, movie_id=None):
        """Get sales breakdown by screen"""
        query = db.session.query(
            Screen.name,
            func.sum(Payment.amount).label('revenue'),
            func.count(Booking.id).label('bookings_count'),
            func.count(BookingSeat.id).label('tickets_sold')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Show, Booking.show_id == Show.id
        ).join(
            Screen, Show.screen_id == Screen.id
        ).filter(
            Show.show_date == report_date
        )
        
        # Apply filters
        if screen_id:
            query = query.filter(Screen.id == screen_id)
        
        if movie_id:
            query = query.filter(Movie.id == movie_id)
        
        return query.group_by(Screen.name).all()
    
    @staticmethod
    def get_occupancy_data(start_date, end_date, screen_id=None, movie_id=None):
        """Get occupancy data for date range"""
        query = db.session.query(
            Show.show_date,
            Show.show_time,
            Movie.title.label('movie_title'),
            Screen.name.label('screen_name'),
            func.count(Seat.id).label('total_seats'),
            func.count(BookingSeat.id).label('seats_sold'),
            func.sum(Payment.amount).label('revenue')
        ).join(
            Booking, Show.id == Booking.show_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Seat, BookingSeat.seat_id == Seat.id
        ).join(
            Payment, Booking.id == Payment.booking_id
        ).join(
            Movie, Show.movie_id == Movie.id
        ).join(
            Screen, Show.screen_id == Screen.id
        ).filter(
            and_(
                Show.show_date >= start_date,
                Show.show_date <= end_date
            )
        )
        
        # Apply filters
        if screen_id:
            query = query.filter(Screen.id == screen_id)
        
        if movie_id:
            query = query.filter(Movie.id == movie_id)
        
        return query.group_by(
            Show.show_date, Show.show_time, Movie.title, Screen.name
        ).all()
    
    @staticmethod
    def get_cashier_performance_data(start_date, end_date, cashier_id=None):
        """Get cashier performance data"""
        query = db.session.query(
            User.id,
            User.username,
            func.count(Booking.id).label('bookings_count'),
            func.sum(Payment.amount).label('revenue'),
            func.avg(Payment.amount).label('average_transaction'),
            func.count(BookingSeat.id).label('tickets_sold')
        ).join(
            Booking, User.id == Booking.user_id
        ).join(
            Payment, Booking.id == Payment.booking_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        )
        
        # Apply cashier filter
        if cashier_id:
            query = query.filter(User.id == cashier_id)
        
        return query.group_by(User.id, User.username).all()
    
    @staticmethod
    def get_movie_performance_data(start_date, end_date, movie_id=None):
        """Get movie performance data"""
        query = db.session.query(
            Movie.id,
            Movie.title,
            func.count(Booking.id).label('bookings_count'),
            func.count(BookingSeat.id).label('tickets_sold'),
            func.sum(Payment.amount).label('revenue'),
            func.avg(Payment.amount).label('average_ticket_price'),
            func.count(func.distinct(Show.show_date)).label('days_running')
        ).join(
            Show, Movie.id == Show.movie_id
        ).join(
            Booking, Show.id == Booking.show_id
        ).join(
            Payment, Booking.id == Payment.booking_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).filter(
            and_(
                Show.show_date >= start_date,
                Show.show_date <= end_date
            )
        )
        
        # Apply movie filter
        if movie_id:
            query = query.filter(Movie.id == movie_id)
        
        return query.group_by(Movie.id, Movie.title).all()
    
    @staticmethod
    def get_screen_utilization_data(start_date, end_date, screen_id=None):
        """Get screen utilization data"""
        query = db.session.query(
            Screen.id,
            Screen.name,
            func.count(Show.id).label('total_shows'),
            func.count(Booking.id).label('total_bookings'),
            func.count(BookingSeat.id).label('total_tickets_sold'),
            func.sum(Payment.amount).label('total_revenue'),
            func.avg(
                func.cast(func.count(BookingSeat.id) * 100.0 / Screen.capacity, db.Float)
            ).label('average_occupancy')
        ).join(
            Show, Screen.id == Show.screen_id
        ).join(
            Booking, Show.id == Booking.show_id, isouter=True
        ).join(
            Payment, Booking.id == Payment.booking_id, isouter=True
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id, isouter=True
        ).filter(
            and_(
                Show.show_date >= start_date,
                Show.show_date <= end_date
            )
        )
        
        # Apply screen filter
        if screen_id:
            query = query.filter(Screen.id == screen_id)
        
        return query.group_by(Screen.id, Screen.name).all()
    
    @staticmethod
    def get_peak_occupancy_times(start_date, end_date):
        """Get peak occupancy times analysis"""
        # Peak day analysis
        peak_day_query = db.session.query(
            Show.show_date,
            func.count(BookingSeat.id).label('seats_sold'),
            func.count(Seat.id).label('total_seats')
        ).join(
            Booking, Show.id == Booking.show_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Seat, Show.screen_id == Seat.screen_id
        ).filter(
            and_(
                Show.show_date >= start_date,
                Show.show_date <= end_date
            )
        ).group_by(Show.show_date).all()
        
        # Peak time analysis
        peak_time_query = db.session.query(
            extract('hour', Show.show_time).label('hour'),
            func.count(BookingSeat.id).label('seats_sold'),
            func.count(Seat.id).label('total_seats')
        ).join(
            Booking, Show.id == Booking.show_id
        ).join(
            BookingSeat, Booking.id == BookingSeat.booking_id
        ).join(
            Seat, Show.screen_id == Seat.screen_id
        ).filter(
            and_(
                Show.show_date >= start_date,
                Show.show_date <= end_date
            )
        ).group_by(extract('hour', Show.show_time)).all()
        
        return {
            'peak_days': peak_day_query,
            'peak_times': peak_time_query
        }
    
    @staticmethod
    def get_payment_method_breakdown(start_date, end_date):
        """Get payment method breakdown"""
        return db.session.query(
            Payment.mode,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total_amount')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(Payment.mode).all()
    
    @staticmethod
    def get_payment_status_breakdown(start_date, end_date):
        """Get payment status breakdown"""
        return db.session.query(
            Payment.status,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total_amount')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(Payment.status).all()
    
    @staticmethod
    def get_payment_trends(start_date, end_date):
        """Get payment trends over time"""
        return db.session.query(
            func.date(Payment.payment_date).label('payment_date'),
            Payment.mode,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total_amount')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(
            func.date(Payment.payment_date), Payment.mode
        ).order_by(func.date(Payment.payment_date)).all()
    
    @staticmethod
    def get_refund_analysis(start_date, end_date):
        """Get refund analysis"""
        return db.session.query(
            Payment.id,
            Payment.amount,
            Payment.refund_amount,
            Payment.refund_reason,
            Payment.refund_method,
            Payment.refunded_at,
            Payment.mode,
            Booking.id.label('booking_id'),
            Movie.title.label('movie_title'),
            User.username.label('cashier_name')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).join(
            Show, Booking.show_id == Show.id
        ).join(
            Movie, Show.movie_id == Movie.id
        ).join(
            User, Booking.user_id == User.id
        ).filter(
            and_(
                Payment.status == 'refunded',
                Payment.refunded_at >= datetime.combine(start_date, datetime.min.time()),
                Payment.refunded_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).all()
    
    @staticmethod
    def get_payment_failure_analysis(start_date, end_date):
        """Get payment failure analysis"""
        return db.session.query(
            Payment.id,
            Payment.amount,
            Payment.mode,
            Payment.failed_at,
            Booking.id.label('booking_id'),
            Movie.title.label('movie_title'),
            User.username.label('cashier_name')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).join(
            Show, Booking.show_id == Show.id
        ).join(
            Movie, Show.movie_id == Movie.id
        ).join(
            User, Booking.user_id == User.id
        ).filter(
            and_(
                Payment.status == 'failed',
                Payment.failed_at >= datetime.combine(start_date, datetime.min.time()),
                Payment.failed_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).all()
    
    @staticmethod
    def get_daily_payment_summary(start_date, end_date):
        """Get daily payment summary"""
        return db.session.query(
            func.date(Payment.payment_date).label('date'),
            func.count(Payment.id).label('total_transactions'),
            func.sum(Payment.amount).label('total_amount'),
            func.sum(func.case([(Payment.status == 'completed', Payment.amount)], else_=0)).label('completed_amount'),
            func.sum(func.case([(Payment.status == 'failed', Payment.amount)], else_=0)).label('failed_amount'),
            func.sum(func.case([(Payment.status == 'refunded', Payment.refund_amount)], else_=0)).label('refunded_amount'),
            func.count(func.case([(Payment.status == 'completed', 1)], else_=None)).label('completed_count'),
            func.count(func.case([(Payment.status == 'failed', 1)], else_=None)).label('failed_count'),
            func.count(func.case([(Payment.status == 'refunded', 1)], else_=None)).label('refunded_count')
        ).join(
            Booking, Payment.booking_id == Booking.id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(
            func.date(Payment.payment_date)
        ).order_by(func.date(Payment.payment_date)).all()
    
    @staticmethod
    def get_customer_behavior_metrics(start_date, end_date):
        """Get customer behavior metrics"""
        # Average tickets per booking
        avg_tickets = db.session.query(
            func.avg(func.count(BookingSeat.id))
        ).join(
            Booking, BookingSeat.booking_id == Booking.id
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).scalar() or 0
        
        # Peak booking times
        peak_booking_hours = db.session.query(
            extract('hour', Booking.booking_time).label('hour'),
            func.count(Booking.id).label('booking_count')
        ).filter(
            and_(
                Booking.booking_time >= datetime.combine(start_date, datetime.min.time()),
                Booking.booking_time <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(extract('hour', Booking.booking_time)).all()
        
        return {
            'avg_tickets_per_booking': avg_tickets,
            'peak_booking_hours': peak_booking_hours
        }