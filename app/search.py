"""
Centralized Search Utility for Cinema Management System

This module provides unified search functionality across all modules in the cinema management system.
It supports advanced querying, filtering, sorting, and pagination for Movies, Shows, Bookings, and Payments.
"""

from datetime import datetime, timedelta
from flask import request
from sqlalchemy import and_, or_, not_, func, desc, asc
from sqlalchemy.orm import joinedload
from app.database import db
from app.movies.models import Movie
from app.shows.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.screens.models import Screen, Seat
from app.auth.models import User


class SearchQuery:
    """Base class for building search queries"""
    
    def __init__(self, model):
        self.model = model
        self.query = model.query
        self.filters = []
        self.search_term = None
        self.sort_field = None
        self.sort_direction = 'asc'
        self.page = 1
        self.per_page = 20
        self.total = 0
        
    def add_filter(self, filter_condition):
        """Add a filter condition to the query"""
        self.filters.append(filter_condition)
        return self
    
    def add_text_search(self, search_term, fields):
        """Add text search across specified fields"""
        if not search_term:
            return self
            
        self.search_term = search_term
        search_conditions = []
        
        for field in fields:
            if hasattr(self.model, field):
                search_conditions.append(getattr(self.model, field).ilike(f'%{search_term}%'))
        
        if search_conditions:
            self.add_filter(or_(*search_conditions))
        
        return self
    
    def add_date_range_filter(self, start_field, start_date=None, end_date=None):
        """Add date range filter"""
        if start_date:
            self.add_filter(getattr(self.model, start_field) >= start_date)
        if end_date:
            self.add_filter(getattr(self.model, start_field) <= end_date)
        return self
    
    def add_enum_filter(self, field, values):
        """Add filter for enum fields"""
        if not values or not isinstance(values, (list, tuple)):
            return self
            
        if hasattr(self.model, field):
            self.add_filter(getattr(self.model, field).in_(values))
        
        return self
    
    def add_numeric_range_filter(self, field, min_value=None, max_value=None):
        """Add numeric range filter"""
        if min_value is not None:
            self.add_filter(getattr(self.model, field) >= min_value)
        if max_value is not None:
            self.add_filter(getattr(self.model, field) <= max_value)
        return self
    
    def add_related_filter(self, relationship_model, relationship_field, search_term):
        """Add filter on related model fields"""
        if not search_term or not hasattr(self.model, relationship_field):
            return self
            
        self.query = self.query.join(getattr(self.model, relationship_field))
        self.add_filter(getattr(relationship_model, relationship_field).ilike(f'%{search_term}%'))
        
        return self
    
    def set_sorting(self, sort_field, sort_direction='asc'):
        """Set sorting for the query"""
        if hasattr(self.model, sort_field):
            self.sort_field = sort_field
            self.sort_direction = sort_direction.lower()
        
        return self
    
    def set_pagination(self, page=1, per_page=20):
        """Set pagination parameters"""
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        
        return self
    
    def execute(self):
        """Execute the query and return paginated results"""
        # Apply all filters
        if self.filters:
            self.query = self.query.filter(and_(*self.filters))
        
        # Apply sorting
        if self.sort_field:
            sort_func = asc if self.sort_direction == 'asc' else desc
            self.query = self.query.order_by(sort_func(getattr(self.model, self.sort_field)))
        
        # Get total count
        self.total = self.query.count()
        
        # Apply pagination
        if self.per_page > 0:
            self.query = self.query.offset((self.page - 1) * self.per_page).limit(self.per_page)
        
        return {
            'results': self.query.all(),
            'total': self.total,
            'page': self.page,
            'per_page': self.per_page,
            'pages': (self.total + self.per_page - 1) // self.per_page if self.per_page > 0 else 1
        }


class SavedSearch(db.Model):
    """Model for storing saved searches"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False)  # movies, shows, bookings, payments
    search_params = db.Column(db.Text, nullable=False)  # JSON string of search parameters
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='saved_searches')
    
    def __repr__(self):
        return f'<SavedSearch {self.name}>'
    
    def to_dict(self):
        """Convert saved search to dictionary"""
        import json
        return {
            'id': self.id,
            'name': self.name,
            'module': self.module,
            'parameters': json.loads(self.search_params) if self.search_params else {},
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class SearchHistory(db.Model):
    """Model for tracking search history"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    search_term = db.Column(db.String(255))
    search_params = db.Column(db.Text)  # JSON string of search parameters
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='search_history')
    
    def __repr__(self):
        return f'<SearchHistory {self.module}: {self.search_term}>'


class MovieSearch(SearchQuery):
    """Specialized search for Movie model"""
    
    def __init__(self):
        super().__init__(Movie)
    
    def search_movies(self, search_term=None, genre=None, language=None, rating=None, 
                     status=None, min_duration=None, max_duration=None, 
                     release_date_from=None, release_date_to=None, 
                     sort_by='name', sort_order='asc'):
        """Advanced movie search with multiple filters"""
        
        # Text search across multiple fields
        if search_term:
            self.add_text_search(search_term, ['name', 'description', 'genre', 'rating'])
        
        # Enum filters
        if genre:
            self.add_filter(Movie.genre.ilike(f'%{genre}%'))
        
        if language:
            self.add_enum_filter('language', language if isinstance(language, list) else [language])
        
        if rating:
            self.add_enum_filter('rating', rating if isinstance(rating, list) else [rating])
        
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        
        # Numeric range filters
        if min_duration is not None or max_duration is not None:
            self.add_numeric_range_filter('duration', min_duration, max_duration)
        
        # Date range filter
        self.add_date_range_filter('release_date', release_date_from, release_date_to)
        
        # Sorting
        self.set_sorting(sort_by, sort_order)
        
        return self


class ShowSearch(SearchQuery):
    """Specialized search for Show model"""
    
    def __init__(self):
        super().__init__(Show)
        # Eager load relationships to avoid N+1 queries
        self.query = self.query.options(joinedload(Show.movie), joinedload(Show.screen))
    
    def search_shows(self, search_term=None, movie_id=None, screen_id=None,
                     show_date_from=None, show_date_to=None, show_time_from=None, show_time_to=None,
                     show_type=None, status=None, min_price=None, max_price=None,
                     sort_by='show_date', sort_order='asc'):
        """Advanced show search with multiple filters"""
        
        # Text search
        if search_term:
            self.add_text_search(search_term, ['show_type'])
        
        # Related model filters
        if search_term and movie_id is None:
            # Search in movie name if not already filtering by movie_id
            self.add_related_filter(Movie, 'name', search_term)
        
        # Direct filters
        if movie_id:
            self.add_filter(Show.movie_id == movie_id)
        
        if screen_id:
            self.add_filter(Show.screen_id == screen_id)
        
        # Date range filters
        self.add_date_range_filter('show_date', show_date_from, show_date_to)
        
        # Time range filters
        if show_time_from:
            self.add_filter(Show.show_time >= show_time_from)
        if show_time_to:
            self.add_filter(Show.show_time <= show_time_to)
        
        # Enum filters
        if show_type:
            self.add_enum_filter('show_type', show_type if isinstance(show_type, list) else [show_type])
        
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        
        # Price range filters
        if min_price is not None or max_price is not None:
            self.add_numeric_range_filter('base_price', min_price, max_price)
        
        # Sorting
        self.set_sorting(sort_by, sort_order)
        
        return self


class BookingSearch(SearchQuery):
    """Specialized search for Booking model"""
    
    def __init__(self):
        super().__init__(Booking)
        # Eager load relationships
        self.query = self.query.options(
            joinedload(Booking.show).joinedload(Show.movie),
            joinedload(Booking.user),
            joinedload(Booking.booking_seats).joinedload(BookingSeat.seat)
        )
    
    def search_bookings(self, search_term=None, reference_number=None, customer_name=None,
                       customer_email=None, customer_phone=None, show_id=None, user_id=None,
                       booking_date_from=None, booking_date_to=None, status=None,
                       payment_method=None, min_amount=None, max_amount=None,
                       sort_by='booking_time', sort_order='desc'):
        """Advanced booking search with multiple filters"""
        
        # Text search
        if search_term:
            self.add_text_search(search_term, ['reference_number', 'customer_name', 'customer_email', 'customer_phone'])
        
        # Direct filters
        if reference_number:
            self.add_filter(Booking.reference_number.ilike(f'%{reference_number}%'))
        
        if customer_name:
            self.add_filter(Booking.customer_name.ilike(f'%{customer_name}%'))
        
        if customer_email:
            self.add_filter(Booking.customer_email.ilike(f'%{customer_email}%'))
        
        if customer_phone:
            self.add_filter(Booking.customer_phone.ilike(f'%{customer_phone}%'))
        
        if show_id:
            self.add_filter(Booking.show_id == show_id)
        
        if user_id:
            self.add_filter(Booking.user_id == user_id)
        
        # Date range filter
        self.add_date_range_filter('booking_time', booking_date_from, booking_date_to)
        
        # Enum filters
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        
        if payment_method:
            self.add_enum_filter('payment_method', payment_method if isinstance(payment_method, list) else [payment_method])
        
        # Amount range filters
        if min_amount is not None or max_amount is not None:
            self.add_numeric_range_filter('total_amount', min_amount, max_amount)
        
        # Sorting
        self.set_sorting(sort_by, sort_order)
        
        return self
    
    # Additional methods for compatibility with route handlers
    def set_search_term(self, search_term):
        """Set search term for text search"""
        if search_term:
            self.add_text_search(search_term, ['reference_number', 'customer_name', 'customer_email', 'customer_phone'])
        return self
    
    def set_search_type(self, search_type):
        """Set search type (placeholder for future implementation)"""
        # For now, just return self - search type logic can be implemented later
        return self
    
    def set_date_range(self, date_from, date_to=None):
        """Set date range for booking search"""
        self.add_date_range_filter('booking_time', date_from, date_to)
        return self
    
    def set_booking_status(self, status):
        """Set booking status filter"""
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        return self
    
    def set_payment_status(self, status):
        """Set payment status filter (maps to booking status for now)"""
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        return self
    
    def set_payment_method(self, method):
        """Set payment method filter"""
        if method:
            self.add_enum_filter('payment_method', method if isinstance(method, list) else [method])
        return self
    
    def set_amount_range(self, min_amount=None, max_amount=None):
        """Set amount range filter"""
        if min_amount is not None or max_amount is not None:
            self.add_numeric_range_filter('total_amount', min_amount, max_amount)
        return self
    
    def set_show_id(self, show_id):
        """Set show ID filter"""
        if show_id:
            self.add_filter(Booking.show_id == show_id)
        return self
    
    def set_customer_email(self, email):
        """Set customer email filter"""
        if email:
            self.add_filter(Booking.customer_email.ilike(f'%{email}%'))
        return self
    
    def set_customer_phone(self, phone):
        """Set customer phone filter"""
        if phone:
            self.add_filter(Booking.customer_phone.ilike(f'%{phone}%'))
        return self
    
    def set_seat_number(self, seat_number):
        """Set seat number filter (placeholder - would need join with BookingSeat)"""
        # This would require a join with BookingSeat table
        # For now, just return self
        return self
    
    def set_sort_by(self, sort_by):
        """Set sort field"""
        if hasattr(Booking, sort_by):
            self.sort_field = sort_by
        return self
    
    def set_pagination(self, page, per_page):
        """Set pagination"""
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        return self
    
    def execute(self):
        """Execute search and return formatted results"""
        result = super().execute()
        
        # Format results for template consumption
        return {
            'items': result['results'],
            'total': result['total'],
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'pages': result['pages'],
                'total': result['total']
            }
        }
    
    def get_autocomplete_suggestions(self, query, search_type='all'):
        """Get autocomplete suggestions for booking search"""
        # Simple implementation - can be enhanced later
        suggestions = []
        
        # Search in customer names
        if search_type in ['all', 'customer']:
            customers = db.session.query(Booking.customer_name).filter(
                Booking.customer_name.ilike(f'%{query}%')
            ).distinct().limit(5).all()
            suggestions.extend([{'type': 'customer', 'value': c[0]} for c in customers])
        
        # Search in reference numbers
        if search_type in ['all', 'reference']:
            refs = db.session.query(Booking.reference_number).filter(
                Booking.reference_number.ilike(f'%{query}%')
            ).distinct().limit(5).all()
            suggestions.extend([{'type': 'reference', 'value': r[0]} for r in refs])
        
        return suggestions


class PaymentSearch(SearchQuery):
    """Specialized search for Payment model"""
    
    def __init__(self):
        super().__init__(Payment)
        # Eager load relationships
        self.query = self.query.options(
            joinedload(Payment.booking).joinedload(Booking.show).joinedload(Show.movie)
        )
    
    def search_payments(self, search_term=None, payment_id=None, reference_id=None,
                       booking_id=None, payment_method=None, status=None,
                       payment_date_from=None, payment_date_to=None,
                       min_amount=None, max_amount=None, sort_by='payment_date', sort_order='desc'):
        """Advanced payment search with multiple filters"""
        
        # Text search
        if search_term:
            self.add_text_search(search_term, ['reference_id', 'paypal_order_id', 'upi_id', 'utr_number'])
        
        # Direct filters
        if payment_id:
            self.add_filter(Payment.id == payment_id)
        
        if reference_id:
            self.add_filter(Payment.reference_id.ilike(f'%{reference_id}%'))
        
        if booking_id:
            self.add_filter(Payment.booking_id == booking_id)
        
        # Date range filter
        self.add_date_range_filter('payment_date', payment_date_from, payment_date_to)
        
        # Enum filters
        if payment_method:
            self.add_enum_filter('mode', payment_method if isinstance(payment_method, list) else [payment_method])
        
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        
        # Amount range filters
        if min_amount is not None or max_amount is not None:
            self.add_numeric_range_filter('amount', min_amount, max_amount)
        
        # Sorting
        self.set_sorting(sort_by, sort_order)
        
        return self
    
    # Additional methods for compatibility with route handlers
    def set_search_term(self, search_term):
        """Set search term for text search"""
        if search_term:
            self.add_text_search(search_term, ['reference_id', 'paypal_order_id', 'upi_id', 'utr_number'])
        return self
    
    def set_search_type(self, search_type):
        """Set search type (placeholder for future implementation)"""
        # For now, just return self - search type logic can be implemented later
        return self
    
    def set_date_range(self, date_from, date_to=None):
        """Set date range for payment search"""
        self.add_date_range_filter('payment_date', date_from, date_to)
        return self
    
    def set_payment_status(self, status):
        """Set payment status filter"""
        if status:
            self.add_enum_filter('status', status if isinstance(status, list) else [status])
        return self
    
    def set_payment_method(self, method):
        """Set payment method filter"""
        if method:
            self.add_enum_filter('mode', method if isinstance(method, list) else [method])
        return self
    
    def set_amount_range(self, min_amount=None, max_amount=None):
        """Set amount range filter"""
        if min_amount is not None or max_amount is not None:
            self.add_numeric_range_filter('amount', min_amount, max_amount)
        return self
    
    def set_booking_id(self, booking_id):
        """Set booking ID filter"""
        if booking_id:
            self.add_filter(Payment.booking_id == booking_id)
        return self
    
    def set_customer_name(self, customer_name):
        """Set customer name filter (via booking relationship)"""
        if customer_name:
            self.query = self.query.join(Booking)
            self.add_filter(Booking.customer_name.ilike(f'%{customer_name}%'))
        return self
    
    def set_customer_email(self, email):
        """Set customer email filter (via booking relationship)"""
        if email:
            self.query = self.query.join(Booking)
            self.add_filter(Booking.customer_email.ilike(f'%{email}%'))
        return self
    
    def set_customer_phone(self, phone):
        """Set customer phone filter (via booking relationship)"""
        if phone:
            self.query = self.query.join(Booking)
            self.add_filter(Booking.customer_phone.ilike(f'%{phone}%'))
        return self
    
    def set_reference_id(self, reference_id):
        """Set reference ID filter"""
        if reference_id:
            self.add_filter(Payment.reference_id.ilike(f'%{reference_id}%'))
        return self
    
    def set_transaction_id(self, transaction_id):
        """Set transaction ID filter (searches in multiple transaction fields)"""
        if transaction_id:
            # Search in various transaction ID fields
            transaction_conditions = [
                Payment.paypal_order_id.ilike(f'%{transaction_id}%'),
                Payment.upi_transaction_id.ilike(f'%{transaction_id}%'),
                Payment.netbanking_transaction_id.ilike(f'%{transaction_id}%'),
                Payment.wallet_transaction_id.ilike(f'%{transaction_id}%'),
                Payment.utr_number.ilike(f'%{transaction_id}%')
            ]
            self.add_filter(or_(*transaction_conditions))
        return self
    
    def set_sort_by(self, sort_by):
        """Set sort field"""
        if hasattr(Payment, sort_by):
            self.sort_field = sort_by
        return self
    
    def set_sort_order(self, sort_order):
        """Set sort order"""
        self.sort_direction = sort_order.lower() if sort_order else 'asc'
        return self
    
    def set_pagination(self, page, per_page):
        """Set pagination"""
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        return self
    
    def execute(self):
        """Execute search and return formatted results"""
        result = super().execute()
        
        # Format results for template consumption
        return {
            'items': result['results'],
            'total': result['total'],
            'pagination': {
                'page': result['page'],
                'per_page': result['per_page'],
                'pages': result['pages'],
                'total': result['total']
            }
        }
    
    def get_autocomplete_suggestions(self, query, search_type='all'):
        """Get autocomplete suggestions for payment search"""
        suggestions = []
        
        # Search in reference IDs
        if search_type in ['all', 'reference']:
            refs = db.session.query(Payment.reference_id).filter(
                Payment.reference_id.ilike(f'%{query}%')
            ).distinct().limit(5).all()
            suggestions.extend([{'type': 'reference', 'value': r[0]} for r in refs if r[0]])
        
        # Search in UPI IDs
        if search_type in ['all', 'upi']:
            upis = db.session.query(Payment.upi_id).filter(
                Payment.upi_id.ilike(f'%{query}%')
            ).distinct().limit(5).all()
            suggestions.extend([{'type': 'upi', 'value': u[0]} for u in upis if u[0]])
        
        return suggestions


class GlobalSearch:
    """Global search across all modules"""
    
    @staticmethod
    def search_all(search_term, limit=10):
        """Search across all modules and return unified results"""
        results = {
            'movies': [],
            'shows': [],
            'bookings': [],
            'payments': []
        }
        
        if not search_term:
            return results
        
        # Search movies
        movie_search = MovieSearch()
        movie_search.add_text_search(search_term, ['name', 'description', 'genre'])
        movie_results = movie_search.set_pagination(1, limit).execute()
        results['movies'] = movie_results['results']
        
        # Search shows
        show_search = ShowSearch()
        show_search.add_related_filter(Movie, 'name', search_term)
        show_search.add_related_filter(Screen, 'name', search_term)
        show_search.add_text_search(search_term, ['show_type'])
        show_results = show_search.set_pagination(1, limit).execute()
        results['shows'] = show_results['results']
        
        # Search bookings
        booking_search = BookingSearch()
        booking_search.add_text_search(search_term, ['reference_number', 'customer_name', 'customer_email'])
        booking_results = booking_search.set_pagination(1, limit).execute()
        results['bookings'] = booking_results['results']
        
        # Search payments
        payment_search = PaymentSearch()
        payment_search.add_text_search(search_term, ['reference_id', 'paypal_order_id', 'upi_id'])
        payment_results = payment_search.set_pagination(1, limit).execute()
        results['payments'] = payment_results['results']
        
        return results


class SearchAnalytics:
    """Search analytics and tracking"""
    
    @staticmethod
    def track_search(user_id, module, search_term, search_params, result_count):
        """Track search in history"""
        history = SearchHistory(
            user_id=user_id,
            module=module,
            search_term=search_term,
            search_params=search_params,
            result_count=result_count
        )
        db.session.add(history)
        db.session.commit()
        return history
    
    @staticmethod
    def save_search(user_id, name, module, search_params, is_default=False):
        """Save a search for later use"""
        saved_search = SavedSearch(
            user_id=user_id,
            name=name,
            module=module,
            search_params=search_params,
            is_default=is_default
        )
        db.session.add(saved_search)
        db.session.commit()
        return saved_search
    
    @staticmethod
    def get_saved_searches(user_id, module=None):
        """Get saved searches for a user"""
        query = SavedSearch.query.filter_by(user_id=user_id)
        if module:
            query = query.filter_by(module=module)
        return query.order_by(SavedSearch.name).all()
    
    @staticmethod
    def get_user_saved_searches(user_id, module=None):
        """Get saved searches for a user (alias for get_saved_searches)"""
        return SearchAnalytics.get_saved_searches(user_id, module)
    
    @staticmethod
    def get_popular_search_terms(days=30, limit=10):
        """Get popular search terms from history"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        return db.session.query(
            SearchHistory.search_term,
            func.count(SearchHistory.id).label('count')
        ).filter(
            SearchHistory.search_term.isnot(None),
            SearchHistory.created_at >= since_date
        ).group_by(
            SearchHistory.search_term
        ).order_by(
            desc('count')
        ).limit(limit).all()
    
    @staticmethod
    def get_popular_searches(module, limit=20):
        """Get popular searches for a specific module"""
        return db.session.query(
            SearchHistory.search_term,
            func.count(SearchHistory.id).label('count'),
            func.avg(SearchHistory.result_count).label('avg_results')
        ).filter(
            SearchHistory.module == module,
            SearchHistory.search_term.isnot(None)
        ).group_by(
            SearchHistory.search_term
        ).order_by(
            desc('count')
        ).limit(limit).all()
    
    @staticmethod
    def get_recent_searches(module, limit=50):
        """Get recent search history for a module"""
        return db.session.query(SearchHistory).filter(
            SearchHistory.module == module
        ).order_by(
            SearchHistory.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_search_performance_by_module(days=30):
        """Get search performance metrics by module"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        return db.session.query(
            SearchHistory.module,
            func.count(SearchHistory.id).label('total_searches'),
            func.avg(SearchHistory.result_count).label('avg_results'),
            func.count(func.nullif(SearchHistory.result_count, 0)).label('searches_with_results')
        ).filter(
            SearchHistory.created_at >= since_date
        ).group_by(
            SearchHistory.module
        ).all()
    
    @staticmethod
    def get_search_performance(module):
        """Get search performance for a specific module"""
        return db.session.query(
            func.count(SearchHistory.id).label('total_searches'),
            func.avg(SearchHistory.result_count).label('avg_results'),
            func.count(func.nullif(SearchHistory.result_count, 0)).label('searches_with_results')
        ).filter(
            SearchHistory.module == module
        ).first()
    
    @staticmethod
    def get_search_parameters(module):
        """Get analysis of search parameters used"""
        # This is a placeholder implementation
        # In a real implementation, you would parse the search_params JSON
        # and analyze parameter usage patterns
        return {
            'common_parameters': ['search_term', 'date_from', 'date_to', 'status'],
            'parameter_frequency': {
                'search_term': 85,
                'date_from': 60,
                'date_to': 55,
                'status': 40
            }
        }
    
    @staticmethod
    def get_optimization_suggestions(module):
        """Get suggestions for search optimization"""
        return [
            "Consider adding autocomplete for frequently searched terms",
            "Optimize search performance for complex queries",
            "Add saved search functionality for power users",
            "Implement search analytics dashboard"
        ]
    
    @staticmethod
    def clear_user_history(user_id, module=None):
        """Clear search history for a user"""
        query = SearchHistory.query.filter_by(user_id=user_id)
        if module:
            query = query.filter_by(module=module)
        
        deleted_count = query.delete()
        db.session.commit()
        return deleted_count
    
    @staticmethod
    def get_search_trends(days=30):
        """Get search trends over time"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        return db.session.query(
            func.date(SearchHistory.created_at).label('date'),
            func.count(SearchHistory.id).label('search_count'),
            func.avg(SearchHistory.result_count).label('avg_results')
        ).filter(
            SearchHistory.created_at >= since_date
        ).group_by(
            func.date(SearchHistory.created_at)
        ).order_by(
            func.date(SearchHistory.created_at)
        ).all()


def get_search_params_from_request(req=None, allowed_params=None):
    """Extract search parameters from Flask request with enhanced error handling"""
    try:
        # Use provided request or default to global request
        target_request = req if req is not None else request
        
        params = {}
        
        try:
            # Get pagination parameters
            params['page'] = target_request.args.get('page', 1, type=int)
            params['per_page'] = target_request.args.get('per_page', 20, type=int)
        except (ValueError, TypeError) as e:
            # Log the error but continue with defaults
            import logging
            logging.getLogger(__name__).warning(f"Error parsing pagination parameters: {e}")
            params['page'] = 1
            params['per_page'] = 20
        
        try:
            # Get sorting parameters
            params['sort_by'] = target_request.args.get('sort_by', 'id')
            params['sort_order'] = target_request.args.get('sort_order', 'asc')
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing sorting parameters: {e}")
            params['sort_by'] = 'id'
            params['sort_order'] = 'asc'
        
        try:
            # Get search term
            params['search_term'] = target_request.args.get('search_term', '').strip()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing search term: {e}")
            params['search_term'] = ''
        
        try:
            # Get date ranges
            params['date_from'] = target_request.args.get('date_from')
            params['date_to'] = target_request.args.get('date_to')
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing date ranges: {e}")
            params['date_from'] = None
            params['date_to'] = None
        
        try:
            # Get numeric ranges
            params['min_value'] = target_request.args.get('min_value', type=float)
            params['max_value'] = target_request.args.get('max_value', type=float)
        except (ValueError, TypeError) as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing numeric ranges: {e}")
            params['min_value'] = None
            params['max_value'] = None
        
        try:
            # Get multi-select parameters
            for key, value in target_request.args.lists():
                if key.endswith('_list'):
                    params[key] = value
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing multi-select parameters: {e}")
        
        try:
            # Get other parameters
            for key in target_request.args:
                if key not in ['page', 'per_page', 'sort_by', 'sort_order', 'search_term', 
                              'date_from', 'date_to', 'min_value', 'max_value'] and not key.endswith('_list'):
                    params[key] = target_request.args.get(key)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error parsing additional parameters: {e}")
        
        # If allowed_params is provided, filter to only those parameters
        if allowed_params:
            try:
                filtered_params = {}
                for param in allowed_params:
                    if param in params:
                        filtered_params[param] = params[param]
                return filtered_params
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Error filtering allowed parameters: {e}")
                # Return all params if filtering fails
                return params
        
        return params
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Critical error in get_search_params_from_request: {e}")
        # Return safe defaults
        return {
            'page': 1,
            'per_page': 20,
            'sort_by': 'id',
            'sort_order': 'asc',
            'search_term': '',
            'date_from': None,
            'date_to': None,
            'min_value': None,
            'max_value': None
        }