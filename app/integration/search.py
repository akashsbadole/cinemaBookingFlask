"""
Global Search Service for Cinema Management System
Provides unified search across all modules
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import or_, and_, func, text
from flask import current_app

from app.database import db
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.shows.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.auth.models import User


class GlobalSearchService:
    """Global search service across all modules"""
    
    @staticmethod
    def search(query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Global search across all modules
        Args:
            query: Search query string
            filters: Optional filters for search (module_type, date_range, etc.)
        Returns:
            Dictionary with search results from all modules
        """
        try:
            filters = filters or {}
            module_type = filters.get('module_type', 'all')
            date_range = filters.get('date_range')
            limit = filters.get('limit', 20)
            
            results = {
                'query': query,
                'filters': filters,
                'total_results': 0,
                'modules': {}
            }
            
            # Search in different modules based on filter
            if module_type in ['all', 'movies']:
                results['modules']['movies'] = GlobalSearchService._search_movies(query, limit)
            
            if module_type in ['all', 'screens']:
                results['modules']['screens'] = GlobalSearchService._search_screens(query, limit)
            
            if module_type in ['all', 'shows']:
                results['modules']['shows'] = GlobalSearchService._search_shows(query, date_range, limit)
            
            if module_type in ['all', 'bookings']:
                results['modules']['bookings'] = GlobalSearchService._search_bookings(query, date_range, limit)
            
            if module_type in ['all', 'payments']:
                results['modules']['payments'] = GlobalSearchService._search_payments(query, date_range, limit)
            
            if module_type in ['all', 'users']:
                results['modules']['users'] = GlobalSearchService._search_users(query, limit)
            
            # Calculate total results
            results['total_results'] = sum(len(module_results) for module_results in results['modules'].values())
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error in global search: {str(e)}")
            return {'error': str(e), 'query': query}
    
    @staticmethod
    def _search_movies(query: str, limit: int) -> List[Dict[str, Any]]:
        """Search in movies module"""
        try:
            movies = Movie.query.filter(
                or_(
                    Movie.name.ilike(f'%{query}%'),
                    Movie.description.ilike(f'%{query}%'),
                    Movie.genre.ilike(f'%{query}%'),
                    Movie.language.ilike(f'%{query}%'),
                    Movie.rating.ilike(f'%{query}%')
                )
            ).limit(limit).all()
            
            return [
                {
                    'id': movie.id,
                    'title': movie.name,
                    'description': movie.description,
                    'genre': movie.genre,
                    'language': movie.language,
                    'rating': movie.rating,
                    'duration': movie.duration,
                    'status': movie.status,
                    'release_date': movie.release_date.isoformat() if movie.release_date else None,
                    'poster_url': movie.poster_url,
                    'type': 'movie',
                    'url': f'/movies/view/{movie.id}',
                    'created_at': movie.created_at.isoformat() if movie.created_at else None
                }
                for movie in movies
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error searching movies: {str(e)}")
            return []
    
    @staticmethod
    def _search_screens(query: str, limit: int) -> List[Dict[str, Any]]:
        """Search in screens module"""
        try:
            screens = Screen.query.filter(
                or_(
                    Screen.name.ilike(f'%{query}%')
                )
            ).limit(limit).all()
            
            results = []
            for screen in screens:
                # Get seat count for this screen
                seat_count = Seat.query.filter_by(screen_id=screen.id).count()
                
                results.append({
                    'id': screen.id,
                    'name': screen.name,
                    'total_rows': screen.total_rows,
                    'total_columns': screen.total_columns,
                    'seat_count': seat_count,
                    'type': 'screen',
                    'url': f'/screens/view/{screen.id}',
                    'created_at': screen.created_at.isoformat() if hasattr(screen, 'created_at') and screen.created_at else None
                })
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error searching screens: {str(e)}")
            return []
    
    @staticmethod
    def _search_shows(query: str, date_range: Dict[str, Any] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search in shows module"""
        try:
            # Build base query
            shows_query = Show.query.join(Movie).join(Screen).filter(
                or_(
                    Movie.name.ilike(f'%{query}%'),
                    Screen.name.ilike(f'%{query}%'),
                    Show.show_type.ilike(f'%{query}%')
                )
            )
            
            # Apply date range filter if provided
            if date_range:
                if 'start_date' in date_range:
                    shows_query = shows_query.filter(Show.show_date >= date_range['start_date'])
                if 'end_date' in date_range:
                    shows_query = shows_query.filter(Show.show_date <= date_range['end_date'])
            
            shows = shows_query.limit(limit).all()
            
            return [
                {
                    'id': show.id,
                    'movie_title': show.movie.name,
                    'screen_name': show.screen.name,
                    'show_date': show.show_date.isoformat(),
                    'show_time': show.show_time.strftime('%H:%M'),
                    'end_time': show.end_time.strftime('%H:%M'),
                    'base_price': float(show.base_price),
                    'show_type': show.show_type,
                    'status': show.status,
                    'occupancy_percentage': show.get_occupancy_percentage(),
                    'available_seats': show.get_available_seats_count(),
                    'total_seats': show.get_total_seats_count(),
                    'type': 'show',
                    'url': f'/shows/view/{show.id}',
                    'created_at': show.created_at.isoformat() if show.created_at else None
                }
                for show in shows
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error searching shows: {str(e)}")
            return []
    
    @staticmethod
    def _search_bookings(query: str, date_range: Dict[str, Any] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search in bookings module"""
        try:
            # Build base query
            bookings_query = Booking.query.join(Show).join(Movie).join(User).filter(
                or_(
                    Booking.reference_number.ilike(f'%{query}%'),
                    Booking.customer_name.ilike(f'%{query}%'),
                    Booking.customer_phone.ilike(f'%{query}%'),
                    Booking.customer_email.ilike(f'%{query}%'),
                    Movie.name.ilike(f'%{query}%'),
                    User.username.ilike(f'%{query}%')
                )
            )
            
            # Apply date range filter if provided
            if date_range:
                if 'start_date' in date_range:
                    bookings_query = bookings_query.filter(Booking.booking_time >= date_range['start_date'])
                if 'end_date' in date_range:
                    bookings_query = bookings_query.filter(Booking.booking_time <= date_range['end_date'])
            
            bookings = bookings_query.limit(limit).all()
            
            results = []
            for booking in bookings:
                # Get seats for this booking
                seats = [f"{bs.seat.row}{bs.seat.column}" for bs in booking.booking_seats]
                
                results.append({
                    'id': booking.id,
                    'reference_number': booking.reference_number,
                    'customer_name': booking.customer_name,
                    'customer_phone': booking.customer_phone,
                    'customer_email': booking.customer_email,
                    'movie_title': booking.show.movie.name,
                    'show_date': booking.show.show_date.isoformat(),
                    'show_time': booking.show.show_time.strftime('%H:%M'),
                    'screen_name': booking.show.screen.name,
                    'total_amount': float(booking.total_amount),
                    'payment_method': booking.payment_method,
                    'status': booking.status,
                    'seats': seats,
                    'seat_count': len(seats),
                    'cashier': booking.user.username if booking.user else None,
                    'type': 'booking',
                    'url': f'/bookings/view/{booking.id}',
                    'booking_time': booking.booking_time.isoformat() if booking.booking_time else None
                })
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error searching bookings: {str(e)}")
            return []
    
    @staticmethod
    def _search_payments(query: str, date_range: Dict[str, Any] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search in payments module"""
        try:
            # Build base query
            payments_query = Payment.query.join(Booking).join(Show).join(Movie).filter(
                or_(
                    Payment.reference_id.ilike(f'%{query}%'),
                    Payment.mode.ilike(f'%{query}%'),
                    Payment.status.ilike(f'%{query}%'),
                    Booking.reference_number.ilike(f'%{query}%'),
                    Movie.name.ilike(f'%{query}%')
                )
            )
            
            # Apply date range filter if provided
            if date_range:
                if 'start_date' in date_range:
                    payments_query = payments_query.filter(Payment.payment_date >= date_range['start_date'])
                if 'end_date' in date_range:
                    payments_query = payments_query.filter(Payment.payment_date <= date_range['end_date'])
            
            payments = payments_query.limit(limit).all()
            
            return [
                {
                    'id': payment.id,
                    'booking_reference': payment.booking.reference_number,
                    'amount': float(payment.amount),
                    'mode': payment.mode,
                    'status': payment.status,
                    'reference_id': payment.reference_id,
                    'movie_title': payment.booking.show.movie.name,
                    'customer_name': payment.booking.customer_name,
                    'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                    'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
                    'type': 'payment',
                    'url': f'/payments/view/{payment.id}',
                    'created_at': payment.created_at.isoformat() if payment.created_at else None
                }
                for payment in payments
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error searching payments: {str(e)}")
            return []
    
    @staticmethod
    def _search_users(query: str, limit: int) -> List[Dict[str, Any]]:
        """Search in users module"""
        try:
            users = User.query.filter(
                or_(
                    User.username.ilike(f'%{query}%'),
                    User.email.ilike(f'%{query}%')
                )
            ).limit(limit).all()
            
            return [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'type': 'user',
                    'url': f'/auth/profile/{user.id}',
                    'created_at': user.created_at.isoformat() if user.created_at else None
                }
                for user in users
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error searching users: {str(e)}")
            return []
    
    @staticmethod
    def advanced_search(search_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advanced search with multiple criteria
        Args:
            search_params: Dictionary with search criteria
        Returns:
            Dictionary with search results
        """
        try:
            module_type = search_params.get('module_type', 'all')
            limit = search_params.get('limit', 50)
            
            results = {
                'search_params': search_params,
                'total_results': 0,
                'modules': {}
            }
            
            if module_type in ['all', 'bookings']:
                results['modules']['bookings'] = GlobalSearchService._advanced_search_bookings(search_params, limit)
            
            if module_type in ['all', 'payments']:
                results['modules']['payments'] = GlobalSearchService._advanced_search_payments(search_params, limit)
            
            if module_type in ['all', 'shows']:
                results['modules']['shows'] = GlobalSearchService._advanced_search_shows(search_params, limit)
            
            # Calculate total results
            results['total_results'] = sum(len(module_results) for module_results in results['modules'].values())
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error in advanced search: {str(e)}")
            return {'error': str(e), 'search_params': search_params}
    
    @staticmethod
    def _advanced_search_bookings(search_params: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Advanced search for bookings"""
        try:
            query = Booking.query.join(Show).join(Movie).join(Screen).join(User)
            
            # Apply filters
            if 'reference_number' in search_params:
                query = query.filter(Booking.reference_number.ilike(f"%{search_params['reference_number']}%"))
            
            if 'customer_name' in search_params:
                query = query.filter(Booking.customer_name.ilike(f"%{search_params['customer_name']}%"))
            
            if 'customer_email' in search_params:
                query = query.filter(Booking.customer_email.ilike(f"%{search_params['customer_email']}%"))
            
            if 'customer_phone' in search_params:
                query = query.filter(Booking.customer_phone.ilike(f"%{search_params['customer_phone']}%"))
            
            if 'movie_id' in search_params:
                query = query.filter(Movie.id == search_params['movie_id'])
            
            if 'screen_id' in search_params:
                query = query.filter(Screen.id == search_params['screen_id'])
            
            if 'status' in search_params:
                query = query.filter(Booking.status == search_params['status'])
            
            if 'payment_method' in search_params:
                query = query.filter(Booking.payment_method == search_params['payment_method'])
            
            if 'user_id' in search_params:
                query = query.filter(Booking.user_id == search_params['user_id'])
            
            if 'amount_min' in search_params:
                query = query.filter(Booking.total_amount >= search_params['amount_min'])
            
            if 'amount_max' in search_params:
                query = query.filter(Booking.total_amount <= search_params['amount_max'])
            
            if 'start_date' in search_params:
                query = query.filter(Booking.booking_time >= search_params['start_date'])
            
            if 'end_date' in search_params:
                query = query.filter(Booking.booking_time <= search_params['end_date'])
            
            bookings = query.limit(limit).all()
            
            results = []
            for booking in bookings:
                seats = [f"{bs.seat.row}{bs.seat.column}" for bs in booking.booking_seats]
                
                results.append({
                    'id': booking.id,
                    'reference_number': booking.reference_number,
                    'customer_name': booking.customer_name,
                    'customer_phone': booking.customer_phone,
                    'customer_email': booking.customer_email,
                    'movie_title': booking.show.movie.name,
                    'screen_name': booking.show.screen.name,
                    'show_date': booking.show.show_date.isoformat(),
                    'show_time': booking.show.show_time.strftime('%H:%M'),
                    'total_amount': float(booking.total_amount),
                    'payment_method': booking.payment_method,
                    'status': booking.status,
                    'seats': seats,
                    'seat_count': len(seats),
                    'cashier': booking.user.username if booking.user else None,
                    'type': 'booking',
                    'url': f'/bookings/view/{booking.id}',
                    'booking_time': booking.booking_time.isoformat() if booking.booking_time else None
                })
            
            return results
            
        except Exception as e:
            current_app.logger.error(f"Error in advanced booking search: {str(e)}")
            return []
    
    @staticmethod
    def _advanced_search_payments(search_params: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Advanced search for payments"""
        try:
            query = Payment.query.join(Booking).join(Show).join(Movie)
            
            # Apply filters
            if 'reference_id' in search_params:
                query = query.filter(Payment.reference_id.ilike(f"%{search_params['reference_id']}%"))
            
            if 'booking_reference' in search_params:
                query = query.filter(Booking.reference_number.ilike(f"%{search_params['booking_reference']}%"))
            
            if 'mode' in search_params:
                query = query.filter(Payment.mode == search_params['mode'])
            
            if 'status' in search_params:
                query = query.filter(Payment.status == search_params['status'])
            
            if 'amount_min' in search_params:
                query = query.filter(Payment.amount >= search_params['amount_min'])
            
            if 'amount_max' in search_params:
                query = query.filter(Payment.amount <= search_params['amount_max'])
            
            if 'start_date' in search_params:
                query = query.filter(Payment.payment_date >= search_params['start_date'])
            
            if 'end_date' in search_params:
                query = query.filter(Payment.payment_date <= search_params['end_date'])
            
            if 'movie_id' in search_params:
                query = query.filter(Movie.id == search_params['movie_id'])
            
            payments = query.limit(limit).all()
            
            return [
                {
                    'id': payment.id,
                    'booking_reference': payment.booking.reference_number,
                    'amount': float(payment.amount),
                    'mode': payment.mode,
                    'status': payment.status,
                    'reference_id': payment.reference_id,
                    'movie_title': payment.booking.show.movie.name,
                    'customer_name': payment.booking.customer_name,
                    'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                    'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
                    'type': 'payment',
                    'url': f'/payments/view/{payment.id}',
                    'created_at': payment.created_at.isoformat() if payment.created_at else None
                }
                for payment in payments
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error in advanced payment search: {str(e)}")
            return []
    
    @staticmethod
    def _advanced_search_shows(search_params: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Advanced search for shows"""
        try:
            query = Show.query.join(Movie).join(Screen)
            
            # Apply filters
            if 'movie_id' in search_params:
                query = query.filter(Movie.id == search_params['movie_id'])
            
            if 'screen_id' in search_params:
                query = query.filter(Screen.id == search_params['screen_id'])
            
            if 'show_type' in search_params:
                query = query.filter(Show.show_type == search_params['show_type'])
            
            if 'status' in search_params:
                query = query.filter(Show.status == search_params['status'])
            
            if 'start_date' in search_params:
                query = query.filter(Show.show_date >= search_params['start_date'])
            
            if 'end_date' in search_params:
                query = query.filter(Show.show_date <= search_params['end_date'])
            
            if 'start_time' in search_params:
                query = query.filter(Show.show_time >= search_params['start_time'])
            
            if 'end_time' in search_params:
                query = query.filter(Show.show_time <= search_params['end_time'])
            
            if 'price_min' in search_params:
                query = query.filter(Show.base_price >= search_params['price_min'])
            
            if 'price_max' in search_params:
                query = query.filter(Show.base_price <= search_params['price_max'])
            
            shows = query.limit(limit).all()
            
            return [
                {
                    'id': show.id,
                    'movie_title': show.movie.name,
                    'screen_name': show.screen.name,
                    'show_date': show.show_date.isoformat(),
                    'show_time': show.show_time.strftime('%H:%M'),
                    'end_time': show.end_time.strftime('%H:%M'),
                    'base_price': float(show.base_price),
                    'show_type': show.show_type,
                    'status': show.status,
                    'occupancy_percentage': show.get_occupancy_percentage(),
                    'available_seats': show.get_available_seats_count(),
                    'total_seats': show.get_total_seats_count(),
                    'type': 'show',
                    'url': f'/shows/view/{show.id}',
                    'created_at': show.created_at.isoformat() if show.created_at else None
                }
                for show in shows
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error in advanced show search: {str(e)}")
            return []
    
    @staticmethod
    def get_search_suggestions(query: str, module_type: str = 'all', limit: int = 10) -> Dict[str, Any]:
        """Get search suggestions for autocomplete"""
        try:
            suggestions = {
                'query': query,
                'module_type': module_type,
                'suggestions': {}
            }
            
            if module_type in ['all', 'movies']:
                # Get movie name suggestions
                movie_suggestions = db.session.query(Movie.name).filter(
                    Movie.name.ilike(f'%{query}%')
                ).limit(limit).all()
                suggestions['suggestions']['movies'] = [s[0] for s in movie_suggestions]
            
            if module_type in ['all', 'bookings']:
                # Get booking reference suggestions
                booking_suggestions = db.session.query(Booking.reference_number).filter(
                    Booking.reference_number.ilike(f'%{query}%')
                ).limit(limit).all()
                suggestions['suggestions']['bookings'] = [s[0] for s in booking_suggestions]
                
                # Get customer name suggestions
                customer_suggestions = db.session.query(Booking.customer_name).filter(
                    Booking.customer_name.ilike(f'%{query}%')
                ).distinct().limit(limit).all()
                suggestions['suggestions']['customers'] = [s[0] for s in customer_suggestions if s[0]]
            
            if module_type in ['all', 'users']:
                # Get username suggestions
                user_suggestions = db.session.query(User.username).filter(
                    User.username.ilike(f'%{query}%')
                ).limit(limit).all()
                suggestions['suggestions']['users'] = [s[0] for s in user_suggestions]
            
            return suggestions
            
        except Exception as e:
            current_app.logger.error(f"Error getting search suggestions: {str(e)}")
            return {'error': str(e), 'query': query}