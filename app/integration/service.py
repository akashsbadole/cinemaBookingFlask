"""
Integration Service for Cinema Management System
Handles cross-module operations and ensures data consistency
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import and_, or_, func, text
from flask import current_app

from app.database import db
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.shows.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment, PaymentStatusHistory
from app.auth.models import User
from app.data_integrity import IntegrityChecker


class IntegrationService:
    """Main integration service for cross-module operations"""
    
    @staticmethod
    def get_dashboard_statistics() -> Dict[str, Any]:
        """Get comprehensive dashboard statistics from all modules"""
        try:
            # Movie statistics
            active_movies = Movie.query.filter_by(status='active').count()
            total_movies = Movie.query.count()
            
            # Screen statistics
            total_screens = Screen.query.count()
            total_seats = Seat.query.count()
            
            # Show statistics
            today_shows = Show.query.filter_by(show_date=datetime.now().date()).count()
            upcoming_shows = Show.query.filter(Show.show_date > datetime.now().date()).count()
            
            # Booking statistics
            today_bookings = Booking.query.filter(
                func.date(Booking.booking_time) == datetime.now().date()
            ).count()
            pending_bookings = Booking.query.filter_by(status='pending').count()
            
            # Payment statistics
            today_revenue = db.session.query(func.sum(Payment.amount)).filter(
                func.date(Payment.payment_date) == datetime.now().date(),
                Payment.status == 'completed'
            ).scalar() or 0
            
            # User statistics
            active_users = User.query.filter_by(is_active=True).count()
            
            # Recent activity
            recent_bookings = Booking.query.order_by(Booking.booking_time.desc()).limit(5).all()
            recent_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(5).all()
            
            return {
                'movies': {
                    'active': active_movies,
                    'total': total_movies,
                    'inactive': total_movies - active_movies
                },
                'screens': {
                    'total': total_screens,
                    'total_seats': total_seats
                },
                'shows': {
                    'today': today_shows,
                    'upcoming': upcoming_shows,
                    'total': today_shows + upcoming_shows
                },
                'bookings': {
                    'today': today_bookings,
                    'pending': pending_bookings,
                    'recent': [booking.to_dict() for booking in recent_bookings]
                },
                'payments': {
                    'today_revenue': float(today_revenue),
                    'recent': [payment.to_dict() for payment in recent_payments]
                },
                'users': {
                    'active': active_users
                },
                'system_health': IntegrityChecker.run_all_checks()['summary']
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting dashboard statistics: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def validate_data_integrity() -> Dict[str, Any]:
        """Run comprehensive data integrity checks across all modules"""
        try:
            integrity_results = IntegrityChecker.run_all_checks()
            
            # Add module-specific checks
            module_checks = {
                'movie_show_integrity': IntegrationService._check_movie_show_integrity(),
                'screen_seat_integrity': IntegrationService._check_screen_seat_integrity(),
                'booking_payment_integrity': IntegrationService._check_booking_payment_integrity(),
                'show_schedule_integrity': IntegrationService._check_show_schedule_integrity()
            }
            
            integrity_results['module_checks'] = module_checks
            
            return integrity_results
            
        except Exception as e:
            current_app.logger.error(f"Error validating data integrity: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _check_movie_show_integrity() -> Dict[str, Any]:
        """Check integrity between movies and shows"""
        try:
            # Check for shows referencing non-existent movies
            orphaned_shows = db.session.query(Show.id, Show.movie_id).outerjoin(
                Movie, Show.movie_id == Movie.id
            ).filter(Movie.id.is_(None)).count()
            
            # Check for active movies without shows
            movies_without_shows = db.session.query(Movie.id, Movie.name).outerjoin(
                Show, Movie.id == Show.movie_id
            ).filter(
                Movie.status == 'active',
                Show.id.is_(None)
            ).count()
            
            return {
                'orphaned_shows': orphaned_shows,
                'active_movies_without_shows': movies_without_shows,
                'status': 'healthy' if orphaned_shows == 0 and movies_without_shows == 0 else 'needs_attention'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 'error'}
    
    @staticmethod
    def _check_screen_seat_integrity() -> Dict[str, Any]:
        """Check integrity between screens and seats"""
        try:
            # Check for seats referencing non-existent screens
            orphaned_seats = db.session.query(Seat.id, Seat.screen_id).outerjoin(
                Screen, Seat.screen_id == Screen.id
            ).filter(Screen.id.is_(None)).count()
            
            # Check for screens without seats
            screens_without_seats = db.session.query(Screen.id, Screen.name).outerjoin(
                Seat, Screen.id == Seat.screen_id
            ).filter(Seat.id.is_(None)).count()
            
            return {
                'orphaned_seats': orphaned_seats,
                'screens_without_seats': screens_without_seats,
                'status': 'healthy' if orphaned_seats == 0 and screens_without_seats == 0 else 'needs_attention'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 'error'}
    
    @staticmethod
    def _check_booking_payment_integrity() -> Dict[str, Any]:
        """Check integrity between bookings and payments"""
        try:
            # Check for payments referencing non-existent bookings
            orphaned_payments = db.session.query(Payment.id, Payment.booking_id).outerjoin(
                Booking, Payment.booking_id == Booking.id
            ).filter(Booking.id.is_(None)).count()
            
            # Check for confirmed bookings without completed payments
            confirmed_bookings_without_payment = db.session.query(Booking.id, Booking.reference_number).outerjoin(
                Payment, Booking.id == Payment.booking_id
            ).filter(
                Booking.status == 'confirmed',
                or_(Payment.id.is_(None), Payment.status != 'completed')
            ).count()
            
            return {
                'orphaned_payments': orphaned_payments,
                'confirmed_bookings_without_payment': confirmed_bookings_without_payment,
                'status': 'healthy' if orphaned_payments == 0 and confirmed_bookings_without_payment == 0 else 'needs_attention'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 'error'}
    
    @staticmethod
    def _check_show_schedule_integrity() -> Dict[str, Any]:
        """Check show scheduling integrity"""
        try:
            # Check for overlapping shows in the same screen
            overlapping_shows = db.session.query(Show.id).filter(
                Show.show_date >= datetime.now().date()
            ).join(
                Show, and_(
                    Show.screen_id == Show.screen_id,
                    Show.show_date == Show.show_date,
                    Show.id < Show.id,
                    or_(
                        and_(Show.show_time <= Show.show_time, Show.end_time > Show.show_time),
                        and_(Show.show_time < Show.show_time, Show.end_time > Show.show_time),
                        and_(Show.show_time >= Show.show_time, Show.show_time < Show.end_time)
                    )
                )
            ).count()
            
            return {
                'overlapping_shows': overlapping_shows,
                'status': 'healthy' if overlapping_shows == 0 else 'needs_attention'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 'error'}
    
    @staticmethod
    def get_cross_module_data(module_type: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get integrated data across multiple modules"""
        try:
            filters = filters or {}
            
            if module_type == 'movie_performance':
                return IntegrationService._get_movie_performance_data(filters)
            elif module_type == 'screen_utilization':
                return IntegrationService._get_screen_utilization_data(filters)
            elif module_type == 'user_activity':
                return IntegrationService._get_user_activity_data(filters)
            elif module_type == 'revenue_analytics':
                return IntegrationService._get_revenue_analytics_data(filters)
            else:
                return []
                
        except Exception as e:
            current_app.logger.error(f"Error getting cross-module data for {module_type}: {str(e)}")
            return []
    
    @staticmethod
    def _get_movie_performance_data(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get movie performance data across shows, bookings, and payments"""
        try:
            query = db.session.query(
                Movie.id,
                Movie.title,
                Movie.genre,
                Movie.language,
                func.count(Show.id).label('total_shows'),
                func.count(Booking.id).label('total_bookings'),
                func.count(BookingSeat.id).label('total_tickets_sold'),
                func.sum(Payment.amount).label('total_revenue'),
                func.avg(Payment.amount).label('average_ticket_price')
            ).outerjoin(
                Show, Movie.id == Show.movie_id
            ).outerjoin(
                Booking, Show.id == Booking.show_id
            ).outerjoin(
                Payment, Booking.id == Payment.booking_id
            ).outerjoin(
                BookingSeat, Booking.id == BookingSeat.booking_id
            ).group_by(Movie.id, Movie.title, Movie.genre, Movie.language)
            
            # Apply filters
            if 'start_date' in filters:
                query = query.filter(Show.show_date >= filters['start_date'])
            if 'end_date' in filters:
                query = query.filter(Show.show_date <= filters['end_date'])
            if 'genre' in filters:
                query = query.filter(Movie.genre == filters['genre'])
            if 'language' in filters:
                query = query.filter(Movie.language == filters['language'])
            
            results = query.all()
            
            return [
                {
                    'movie_id': result.id,
                    'title': result.title,
                    'genre': result.genre,
                    'language': result.language,
                    'total_shows': result.total_shows or 0,
                    'total_bookings': result.total_bookings or 0,
                    'total_tickets_sold': result.total_tickets_sold or 0,
                    'total_revenue': float(result.total_revenue or 0),
                    'average_ticket_price': float(result.average_ticket_price or 0)
                }
                for result in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting movie performance data: {str(e)}")
            return []
    
    @staticmethod
    def _get_screen_utilization_data(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get screen utilization data across shows and bookings"""
        try:
            query = db.session.query(
                Screen.id,
                Screen.name,
                func.count(Seat.id).label('total_seats'),
                func.count(Show.id).label('total_shows'),
                func.count(Booking.id).label('total_bookings'),
                func.count(BookingSeat.id).label('total_tickets_sold'),
                func.sum(Payment.amount).label('total_revenue')
            ).outerjoin(
                Seat, Screen.id == Seat.screen_id
            ).outerjoin(
                Show, Screen.id == Show.screen_id
            ).outerjoin(
                Booking, Show.id == Booking.show_id
            ).outerjoin(
                Payment, Booking.id == Payment.booking_id
            ).outerjoin(
                BookingSeat, Booking.id == BookingSeat.booking_id
            ).group_by(Screen.id, Screen.name)
            
            # Apply filters
            if 'start_date' in filters:
                query = query.filter(Show.show_date >= filters['start_date'])
            if 'end_date' in filters:
                query = query.filter(Show.show_date <= filters['end_date'])
            if 'screen_id' in filters:
                query = query.filter(Screen.id == filters['screen_id'])
            
            results = query.all()
            
            return [
                {
                    'screen_id': result.id,
                    'screen_name': result.name,
                    'total_seats': result.total_seats or 0,
                    'total_shows': result.total_shows or 0,
                    'total_bookings': result.total_bookings or 0,
                    'total_tickets_sold': result.total_tickets_sold or 0,
                    'total_revenue': float(result.total_revenue or 0),
                    'utilization_percentage': round(
                        (result.total_tickets_sold or 0) / (result.total_seats or 1) * 100, 2
                    )
                }
                for result in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting screen utilization data: {str(e)}")
            return []
    
    @staticmethod
    def _get_user_activity_data(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get user activity data across bookings and payments"""
        try:
            query = db.session.query(
                User.id,
                User.username,
                User.role,
                func.count(Booking.id).label('total_bookings'),
                func.sum(Payment.amount).label('total_revenue'),
                func.avg(Payment.amount).label('average_transaction'),
                func.count(BookingSeat.id).label('total_tickets_processed')
            ).outerjoin(
                Booking, User.id == Booking.user_id
            ).outerjoin(
                Payment, Booking.id == Payment.booking_id
            ).outerjoin(
                BookingSeat, Booking.id == BookingSeat.booking_id
            ).group_by(User.id, User.username, User.role)
            
            # Apply filters
            if 'start_date' in filters:
                query = query.filter(Booking.booking_time >= filters['start_date'])
            if 'end_date' in filters:
                query = query.filter(Booking.booking_time <= filters['end_date'])
            if 'role' in filters:
                query = query.filter(User.role == filters['role'])
            if 'user_id' in filters:
                query = query.filter(User.id == filters['user_id'])
            
            results = query.all()
            
            return [
                {
                    'user_id': result.id,
                    'username': result.username,
                    'role': result.role,
                    'total_bookings': result.total_bookings or 0,
                    'total_revenue': float(result.total_revenue or 0),
                    'average_transaction': float(result.average_transaction or 0),
                    'total_tickets_processed': result.total_tickets_processed or 0
                }
                for result in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting user activity data: {str(e)}")
            return []
    
    @staticmethod
    def _get_revenue_analytics_data(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get revenue analytics data across multiple dimensions"""
        try:
            # Group by date for revenue trends
            query = db.session.query(
                func.date(Payment.payment_date).label('date'),
                func.count(Payment.id).label('transaction_count'),
                func.sum(Payment.amount).label('total_revenue'),
                func.avg(Payment.amount).label('average_transaction'),
                Payment.mode.label('payment_method')
            ).join(
                Booking, Payment.booking_id == Booking.id
            ).group_by(
                func.date(Payment.payment_date),
                Payment.mode
            )
            
            # Apply filters
            if 'start_date' in filters:
                query = query.filter(Payment.payment_date >= filters['start_date'])
            if 'end_date' in filters:
                query = query.filter(Payment.payment_date <= filters['end_date'])
            if 'payment_method' in filters:
                query = query.filter(Payment.mode == filters['payment_method'])
            
            results = query.all()
            
            return [
                {
                    'date': result.date.isoformat() if result.date else None,
                    'transaction_count': result.transaction_count,
                    'total_revenue': float(result.total_revenue or 0),
                    'average_transaction': float(result.average_transaction or 0),
                    'payment_method': result.payment_method
                }
                for result in results
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting revenue analytics data: {str(e)}")
            return []
    
    @staticmethod
    def cascade_delete_movie(movie_id: int) -> Dict[str, Any]:
        """Safely delete a movie with cascade operations"""
        try:
            movie = Movie.query.get(movie_id)
            if not movie:
                return {'success': False, 'error': 'Movie not found'}
            
            # Check for existing shows
            shows = Show.query.filter_by(movie_id=movie_id).all()
            if shows:
                # Check for bookings in these shows
                show_ids = [show.id for show in shows]
                bookings = Booking.query.filter(Booking.show_id.in_(show_ids)).all()
                
                if bookings:
                    return {
                        'success': False,
                        'error': 'Cannot delete movie with existing bookings',
                        'affected_bookings': len(bookings)
                    }
            
            # Delete shows first
            for show in shows:
                db.session.delete(show)
            
            # Delete the movie
            db.session.delete(movie)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Movie deleted successfully',
                'deleted_shows': len(shows)
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting movie {movie_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def cascade_delete_screen(screen_id: int) -> Dict[str, Any]:
        """Safely delete a screen with cascade operations"""
        try:
            screen = Screen.query.get(screen_id)
            if not screen:
                return {'success': False, 'error': 'Screen not found'}
            
            # Check for existing shows
            shows = Show.query.filter_by(screen_id=screen_id).all()
            if shows:
                # Check for bookings in these shows
                show_ids = [show.id for show in shows]
                bookings = Booking.query.filter(Booking.show_id.in_(show_ids)).all()
                
                if bookings:
                    return {
                        'success': False,
                        'error': 'Cannot delete screen with existing bookings',
                        'affected_bookings': len(bookings)
                    }
            
            # Delete seats first
            seats = Seat.query.filter_by(screen_id=screen_id).all()
            for seat in seats:
                db.session.delete(seat)
            
            # Delete shows
            for show in shows:
                db.session.delete(show)
            
            # Delete the screen
            db.session.delete(screen)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Screen deleted successfully',
                'deleted_shows': len(shows),
                'deleted_seats': len(seats)
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting screen {screen_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def cascade_delete_user(user_id: int) -> Dict[str, Any]:
        """Safely delete a user with cascade operations"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Check for existing bookings
            bookings = Booking.query.filter_by(user_id=user_id).all()
            if bookings:
                # Check for confirmed bookings
                confirmed_bookings = [b for b in bookings if b.status == 'confirmed']
                if confirmed_bookings:
                    return {
                        'success': False,
                        'error': 'Cannot delete user with confirmed bookings',
                        'affected_bookings': len(confirmed_bookings)
                    }
            
            # Cancel pending bookings
            for booking in bookings:
                if booking.status == 'pending':
                    booking.status = 'cancelled'
                    # Release seat locks
                    for booking_seat in booking.booking_seats:
                        db.session.delete(booking_seat)
            
            # Mark user as inactive instead of deleting
            user.is_active = False
            db.session.commit()
            
            return {
                'success': True,
                'message': 'User deactivated successfully',
                'cancelled_bookings': len([b for b in bookings if b.status == 'cancelled'])
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting user {user_id}: {str(e)}")
            return {'success': False, 'error': str(e)}