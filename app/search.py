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


def get_search_params_from_request():
    """Extract search parameters from Flask request"""
    params = {}
    
    # Get pagination parameters
    params['page'] = request.args.get('page', 1, type=int)
    params['per_page'] = request.args.get('per_page', 20, type=int)
    
    # Get sorting parameters
    params['sort_by'] = request.args.get('sort_by', 'id')
    params['sort_order'] = request.args.get('sort_order', 'asc')
    
    # Get search term
    params['search_term'] = request.args.get('search_term', '').strip()
    
    # Get date ranges
    params['date_from'] = request.args.get('date_from')
    params['date_to'] = request.args.get('date_to')
    
    # Get numeric ranges
    params['min_value'] = request.args.get('min_value', type=float)
    params['max_value'] = request.args.get('max_value', type=float)
    
    # Get multi-select parameters
    for key, value in request.args.lists():
        if key.endswith('_list'):
            params[key] = value
    
    # Get other parameters
    for key in request.args:
        if key not in ['page', 'per_page', 'sort_by', 'sort_order', 'search_term', 
                      'date_from', 'date_to', 'min_value', 'max_value'] and not key.endswith('_list'):
            params[key] = request.args.get(key)
    
    return params