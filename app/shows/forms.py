"""
Shows Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField, DateField, TimeField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from wtforms.widgets import TextInput
from datetime import datetime, time
from app.validators import DataValidators, InputSanitizer, SecurityValidator
import json


class ShowForm(FlaskForm):
    """Show form for adding and editing shows"""
    movie_id = SelectField('Movie', coerce=int, validators=[DataRequired()])
    screen_id = SelectField('Screen', coerce=int, validators=[DataRequired()])
    show_date = DateField('Show Date', validators=[DataRequired()], format='%Y-%m-%d')
    show_time = TimeField('Show Time', validators=[DataRequired()])
    base_price = DecimalField('Base Price', validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be positive')
    ], places=2)
    weekend_surcharge = DecimalField('Weekend Surcharge', default=0.00, validators=[
        NumberRange(min=0, message='Surcharge must be non-negative')
    ], places=2)
    matinee_discount = DecimalField('Matinee Discount', default=0.00, validators=[
        NumberRange(min=0, message='Discount must be non-negative')
    ], places=2)
    show_type = SelectField('Show Type', choices=[
        ('regular', 'Regular'),
        ('matinee', 'Matinee'),
        ('evening', 'Evening'),
        ('night', 'Night')
    ], default='regular')
    submit = SubmitField('Save Show')
    
    def __init__(self, *args, **kwargs):
        super(ShowForm, self).__init__(*args, **kwargs)
        # Populate movie choices
        from app.movies.models import Movie
        self.movie_id.choices = [(m.id, m.name) for m in Movie.query.filter_by(status='active').order_by(Movie.name).all()]
        
        # Populate screen choices
        from app.screens.models import Screen
        self.screen_id.choices = [(s.id, s.name) for s in Screen.query.order_by(Screen.name).all()]
    
    def validate_show_date(self, field):
        """Validate that show date is not in the past"""
        if field.data and field.data < datetime.now().date():
            raise ValidationError('Show date cannot be in the past')
    
    def validate_show_time(self, field):
        """Validate show time is within business hours"""
        if field.data:
            hour = field.data.hour
            if hour < 6 or hour > 23:
                raise ValidationError('Show time must be between 6:00 AM and 11:59 PM')
    
    def validate_base_price(self, field):
        """Validate minimum price"""
        if field.data and field.data < 50:
            raise ValidationError('Base price must be at least ₹50')


class ShowSearchForm(FlaskForm):
    """Form for searching shows with enhanced validation"""
    search = StringField('Search', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    movie_id = SelectField('Movie', coerce=int, validators=[Optional()])
    screen_id = SelectField('Screen', coerce=int, validators=[Optional()])
    show_type = SelectField('Show Type', choices=[
        ('', 'All Types'),
        ('regular', 'Regular'),
        ('matinee', 'Matinee'),
        ('evening', 'Evening'),
        ('night', 'Night')
    ], validators=[Optional()])
    status = SelectField('Status', choices=[
        ('', 'All Status'),
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed')
    ], validators=[Optional()])
    
    # Date and time filters
    date_from = DateField('Date From', validators=[Optional()])
    date_to = DateField('Date To', validators=[Optional()])
    time_from = TimeField('Time From', validators=[Optional()])
    time_to = TimeField('Time To', validators=[Optional()])
    
    # Price range filters
    min_price = DecimalField('Min Price', validators=[
        Optional(),
        NumberRange(min=0, message='Price must be non-negative')
    ], places=2)
    max_price = DecimalField('Max Price', validators=[
        Optional(),
        NumberRange(min=0, message='Price must be non-negative')
    ], places=2)
    
    # Occupancy filters
    min_occupancy = IntegerField('Min Occupancy (%)', validators=[
        Optional(),
        NumberRange(min=0, max=100, message='Occupancy must be between 0 and 100')
    ])
    max_occupancy = IntegerField('Max Occupancy (%)', validators=[
        Optional(),
        NumberRange(min=0, max=100, message='Occupancy must be between 0 and 100')
    ])
    
    # Sorting options
    sort_by = SelectField('Sort By', choices=[
        ('show_date', 'Date'),
        ('show_time', 'Time'),
        ('base_price', 'Price'),
        ('created_at', 'Created'),
        ('occupancy', 'Occupancy')
    ], default='show_date', validators=[Optional()])
    sort_order = SelectField('Sort Order', choices=[
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ], default='asc', validators=[Optional()])
    
    # Pagination
    per_page = SelectField('Results per page', choices=[
        ('10', '10'),
        ('25', '25'),
        ('50', '50'),
        ('100', '100')
    ], default='25', validators=[Optional()])
    
    # Actions
    submit = SubmitField('Search')
    clear = SubmitField('Clear Filters')
    save_search = SubmitField('Save Search')
    search_name = StringField('Search Name', validators=[
        Optional(),
        Length(max=100, message='Search name cannot exceed 100 characters')
    ])
    
    def __init__(self, *args, **kwargs):
        super(ShowSearchForm, self).__init__(*args, **kwargs)
        # Populate movie choices
        from app.movies.models import Movie
        self.movie_id.choices = [(0, 'All Movies')] + [(m.id, m.name) for m in Movie.query.filter_by(status='active').order_by(Movie.name).all()]
        
        # Populate screen choices
        from app.screens.models import Screen
        self.screen_id.choices = [(0, 'All Screens')] + [(s.id, s.name) for s in Screen.query.order_by(Screen.name).all()]
    
    def validate_search(self, field):
        """Validate and sanitize search term"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Check for empty search after sanitization
            if not sanitized.strip():
                raise ValidationError('Please enter a valid search term')
    
    def validate_date_to(self, field):
        """Validate date range"""
        if field.data and self.date_from.data:
            if field.data < self.date_from.data:
                raise ValidationError('End date must be after start date')
    
    def validate_time_to(self, field):
        """Validate time range"""
        if field.data and self.time_from.data:
            if field.data < self.time_from.data:
                raise ValidationError('End time must be after start time')
    
    def validate_min_price(self, field):
        """Validate price range"""
        if field.data and self.max_price.data:
            if field.data > self.max_price.data:
                raise ValidationError('Minimum price cannot be greater than maximum price')
    
    def validate_min_occupancy(self, field):
        """Validate occupancy range"""
        if field.data and self.max_occupancy.data:
            if field.data > self.max_occupancy.data:
                raise ValidationError('Minimum occupancy cannot be greater than maximum occupancy')


class AdvancedShowSearchForm(ShowSearchForm):
    """Extended form for advanced show search with additional filters"""
    
    # Advanced filters
    has_bookings = SelectField('Booking Status', choices=[
        ('', 'All Shows'),
        ('with_bookings', 'With Bookings'),
        ('without_bookings', 'Without Bookings')
    ], validators=[Optional()])
    
    # Additional sorting options
    sort_by = SelectField('Sort By', choices=[
        ('show_date', 'Date'),
        ('show_time', 'Time'),
        ('base_price', 'Price'),
        ('created_at', 'Created'),
        ('occupancy', 'Occupancy'),
        ('screen_name', 'Screen Name'),
        ('movie_name', 'Movie Name')
    ], default='show_date', validators=[Optional()])
    
    # Date presets
    date_preset = SelectField('Date Range', choices=[
        ('', 'Custom Range'),
        ('today', 'Today'),
        ('tomorrow', 'Tomorrow'),
        ('this_week', 'This Week'),
        ('next_week', 'Next Week'),
        ('this_month', 'This Month'),
        ('next_month', 'Next Month')
    ], validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(AdvancedShowSearchForm, self).__init__(*args, **kwargs)