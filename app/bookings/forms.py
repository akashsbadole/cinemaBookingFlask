"""
Bookings Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, DecimalField, SubmitField, TelField, EmailField, IntegerField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Email, ValidationError
from wtforms.widgets import TextArea
from datetime import datetime, time, timedelta
import re
from app.validators import (
    BusinessValidators, DataValidators, InputSanitizer,
    SecurityValidator, CrossFieldValidators, validate_seat_availability
)
from app.enhanced_validators import (
    BusinessRuleValidators, DatabaseConstraintValidators, ValidationAuditor
)
from app.shows.models import Show
from app.movies.models import Movie
from app.screens.models import Screen


class BookingForm(FlaskForm):
    """Main booking form for customer information and payment details"""
    customer_name = StringField('Customer Name', validators=[
        DataRequired(message='Customer name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    customer_phone = TelField('Phone Number', validators=[
        DataRequired(message='Phone number is required'),
        Length(min=10, max=15, message='Please enter a valid phone number')
    ])
    customer_email = EmailField('Email Address', validators=[
        Optional(),
        Email(message='Please enter a valid email address')
    ])
    show_id = SelectField('Show', coerce=int, validators=[
        DataRequired(message='Please select a show')
    ])
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI')
    ], validators=[DataRequired(message='Please select a payment method')])
    payment_reference = StringField('Payment Reference', validators=[
        Optional(),
        Length(max=100, message='Reference cannot exceed 100 characters')
    ])
    total_amount = DecimalField('Total Amount', validators=[
        DataRequired(message='Total amount is required'),
        NumberRange(min=0, message='Amount must be positive')
    ], places=2)
    submit = SubmitField('Confirm Booking')
    
    def __init__(self, *args, **kwargs):
        super(BookingForm, self).__init__(*args, **kwargs)
        # Only populate show choices if not already set (for edit cases)
        if not self.show_id.data or len(self.show_id.choices) == 0:
            self._populate_show_choices()
    
    def _populate_show_choices(self):
        """Populate show choices with available shows"""
        shows = Show.query.filter_by(status='scheduled').join(Movie).filter(
            Movie.status == 'active'
        ).join(Screen).filter(
            Show.show_date >= datetime.now().date()
        ).order_by(Show.show_date, Show.show_time).all()
        
        self.show_id.choices = [(0, 'Select a Show')]
        for show in shows:
            display_text = f"{show.movie.name} - {show.show_date.strftime('%d %b %Y')} at {show.show_time.strftime('%I:%M %p')} - {show.screen.name}"
            self.show_id.choices.append((show.id, display_text))
    
    def validate_customer_name(self, field):
        """Validate and sanitize customer name"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            if not sanitized:
                raise ValidationError('Customer name cannot be empty')
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in customer name')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in customer name')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_phone(self, field):
        """Validate and sanitize phone number"""
        if field.data:
            # Sanitize phone number
            sanitized = InputSanitizer.sanitize_phone(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid 10-digit phone number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_email(self, field):
        """Validate and sanitize email address"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid email address')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_payment_reference(self, field):
        """Validate payment reference based on payment method"""
        payment_method = self.payment_method.data if self.payment_method.data else None
        
        if payment_method in ['card', 'upi'] and not field.data:
            raise ValidationError(f'Payment reference is required for {payment_method} payments')
        
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in payment reference')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_total_amount(self, field):
        """Validate total amount with business rules"""
        if field.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(
                field.data,
                min_val=0.01,
                max_val=50000,  # Maximum reasonable amount
                decimal_places=2
            )
            
            if sanitized is None:
                raise ValidationError('Invalid amount format')
            
            # Validate payment method limits
            payment_method = self.payment_method.data if self.payment_method.data else None
            if payment_method:
                from flask_login import current_user
                user_id = current_user.id if current_user.is_authenticated else None
                
                payment_valid, payment_error = BusinessRuleValidators.validate_payment_method_limits(
                    user_id, payment_method, sanitized
                )
                
                if not payment_valid:
                    raise ValidationError(payment_error)
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_show_id(self, field):
        """Validate show selection with business rules"""
        if field.data and field.data > 0:
            from flask_login import current_user
            
            # Validate booking time restrictions
            time_valid, time_error = BusinessRuleValidators.validate_booking_time_restrictions(
                field.data,
                current_user.id if current_user.is_authenticated else None
            )
            
            if not time_valid:
                raise ValidationError(time_error)


class SeatSelectionForm(FlaskForm):
    """Form for seat selection with validation"""
    show_id = HiddenField(validators=[DataRequired(message='Show is required')])
    selected_seats = HiddenField(validators=[DataRequired(message='Please select at least one seat')])
    action = SelectField('Action', choices=[
        ('select', 'Select Seats'),
        ('lock', 'Lock Seats'),
        ('release', 'Release Seats')
    ], default='select')
    submit = SubmitField('Submit')
    
    def validate_selected_seats(self, field):
        """Validate selected seats format and availability with enhanced checks"""
        if field.data:
            # Parse seat data (expecting format like "A1,A2,A3")
            seat_ids = [int(sid.strip()) for sid in field.data.split(',') if sid.strip()]
            
            if len(seat_ids) > 10:
                raise ValidationError('Maximum 10 seats can be booked at once')
            
            # Validate seat ID format
            invalid_seats = []
            for seat_id in seat_ids:
                if not isinstance(seat_id, int) or seat_id <= 0:
                    invalid_seats.append(seat_id)
            
            if invalid_seats:
                raise ValidationError(f'Invalid seat selection: {invalid_seats}')
            
            # Validate seat availability if show_id is provided
            show_id = self.show_id.data
            if show_id:
                # Use existing validator for basic availability
                is_valid, error_message = BusinessValidators.validate_seat_availability(show_id, seat_ids)
                if not is_valid:
                    raise ValidationError(error_message)
                
                # Enhanced validation: Check pricing rules
                # We'll need the total amount for this, but it's not in this form
                # This could be added as a hidden field or validated at the next step


class ShowSelectionForm(FlaskForm):
    """Form for selecting shows based on movie, date, and screen"""
    movie_id = SelectField('Movie', coerce=int, validators=[Optional()])
    screen_id = SelectField('Screen', coerce=int, validators=[Optional()])
    show_date = SelectField('Date', coerce=int, validators=[Optional()])
    submit = SubmitField('Find Shows')
    
    def __init__(self, *args, **kwargs):
        super(ShowSelectionForm, self).__init__(*args, **kwargs)
        # Populate movie choices
        from app.movies.models import Movie
        movies = Movie.query.filter_by(status='active').order_by(Movie.name).all()
        self.movie_id.choices = [(0, 'All Movies')] + [(m.id, m.name) for m in movies]
        
        # Populate screen choices
        from app.screens.models import Screen
        screens = Screen.query.order_by(Screen.name).all()
        self.screen_id.choices = [(0, 'All Screens')] + [(s.id, s.name) for s in screens]
        
        # Populate date choices (next 7 days)
        self.show_date.choices = [(0, 'All Dates')]
        for i in range(7):
            date_obj = datetime.now().date() + timedelta(days=i)
            date_str = date_obj.strftime('%d %b %Y')
            date_int = int(date_obj.strftime('%Y%m%d'))
            self.show_date.choices.append((date_int, date_str))
    
    def validate_show_date(self, field):
        """Validate selected date"""
        if field.data and field.data != 0:
            try:
                date_int = int(field.data)
                date_obj = datetime.strptime(str(date_int), '%Y%m%d').date()
                
                # Don't allow dates more than 30 days in the future
                if date_obj > datetime.now().date() + datetime.timedelta(days=30):
                    raise ValidationError('Cannot select shows more than 30 days in advance')
                
                # Don't allow dates in the past
                if date_obj < datetime.now().date():
                    raise ValidationError('Cannot select shows from past dates')
                    
            except ValueError:
                raise ValidationError('Invalid date selection')


class BookingSearchForm(FlaskForm):
    """Form for searching bookings with enhanced validation"""
    search_term = StringField('Search', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    search_type = SelectField('Search By', choices=[
        ('all', 'All Fields'),
        ('customer', 'Customer Name'),
        ('movie', 'Movie Title'),
        ('booking_id', 'Booking ID')
    ], default='all')
    date_from = SelectField('From Date', coerce=int, validators=[Optional()])
    date_to = SelectField('To Date', coerce=int, validators=[Optional()])
    submit = SubmitField('Search')
    
    def __init__(self, *args, **kwargs):
        super(BookingSearchForm, self).__init__(*args, **kwargs)
        # Populate date choices (last 30 days and next 7 days)
        self.date_from.choices = [(0, 'Any Date')]
        self.date_to.choices = [(0, 'Any Date')]
        
        for i in range(30):
            date_obj = datetime.now().date() - timedelta(days=i)
            date_str = date_obj.strftime('%d %b %Y')
            date_int = int(date_obj.strftime('%Y%m%d'))
            self.date_from.choices.append((date_int, date_str))
            self.date_to.choices.append((date_int, date_str))
    
    def validate_search_term(self, field):
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
    
    def validate_date_range(self):
        """Validate date range selection"""
        date_from = self.date_from.data if self.date_from.data else 0
        date_to = self.date_to.data if self.date_to.data else 0
        
        if date_from != 0 and date_to != 0 and date_from > date_to:
            raise ValidationError('From date cannot be after to date')
        
        # Limit date range to 30 days
        if date_from != 0 and date_to != 0:
            days_diff = date_to - date_from
            if days_diff > 300000:  # YYMMDD format, so 300000 = 30 days
                raise ValidationError('Date range cannot exceed 30 days')


class SeatLockForm(FlaskForm):
    """Form for temporarily locking seats during selection"""
    show_id = HiddenField(validators=[DataRequired(message='Show ID is required')])
    seat_ids = HiddenField(validators=[DataRequired(message='Seat IDs are required')])
    lock_duration = SelectField('Lock Duration', choices=[
        (5, '5 minutes'),
        (10, '10 minutes'),
        (15, '15 minutes')
    ], default=10, coerce=int)
    submit = SubmitField('Lock Seats')
    
    def validate_seat_ids(self, field):
        """Validate seat IDs format"""
        if field.data:
            # Parse seat data
            seat_ids = [int(sid.strip()) for sid in field.data.split(',') if sid.strip()]
            
            if len(seat_ids) > 10:
                raise ValidationError('Maximum 10 seats can be locked at once')
            
            # Validate seat ID format
            invalid_seats = []
            for seat_id in seat_ids:
                if not isinstance(seat_id, int) or seat_id <= 0:
                    invalid_seats.append(seat_id)
            
            if invalid_seats:
                raise ValidationError(f'Invalid seat IDs: {invalid_seats}')


class AdvancedBookingSearchForm(FlaskForm):
    """Advanced search form for bookings with comprehensive filtering"""
    # Basic search
    search_term = StringField('Search Term', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    search_type = SelectField('Search By', choices=[
        ('all', 'All Fields'),
        ('customer', 'Customer Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('movie', 'Movie Title'),
        ('booking_id', 'Booking ID'),
        ('reference', 'Reference Number'),
        ('seat', 'Seat Number')
    ], default='all')
    
    # Date range
    date_from = StringField('From Date', validators=[Optional()])
    date_to = StringField('To Date', validators=[Optional()])
    
    # Status filters
    booking_status = SelectField('Booking Status', choices=[
        ('', 'All Statuses'),
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled')
    ], validators=[Optional()])
    
    payment_status = SelectField('Payment Status', choices=[
        ('', 'All Payment Status'),
        ('completed', 'Completed'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ], validators=[Optional()])
    
    payment_method = SelectField('Payment Method', choices=[
        ('', 'All Methods'),
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('net_banking', 'Net Banking')
    ], validators=[Optional()])
    
    # Amount range
    amount_min = DecimalField('Min Amount', validators=[
        Optional(),
        NumberRange(min=0, message='Amount must be positive')
    ], places=2)
    amount_max = DecimalField('Max Amount', validators=[
        Optional(),
        NumberRange(min=0, message='Amount must be positive')
    ], places=2)
    
    # Show filter
    show_id = SelectField('Show', coerce=int, validators=[Optional()])
    
    # Customer filters
    customer_email = EmailField('Customer Email', validators=[Optional()])
    customer_phone = TelField('Customer Phone', validators=[Optional()])
    
    # Seat filter
    seat_number = StringField('Seat Number', validators=[
        Optional(),
        Length(max=10, message='Seat number cannot exceed 10 characters')
    ])
    
    # Sorting and pagination
    sort_by = SelectField('Sort By', choices=[
        ('booking_time_desc', 'Booking Time (Newest)'),
        ('booking_time_asc', 'Booking Time (Oldest)'),
        ('show_date_asc', 'Show Date (Upcoming)'),
        ('show_date_desc', 'Show Date (Past)'),
        ('customer_name_asc', 'Customer Name (A-Z)'),
        ('customer_name_desc', 'Customer Name (Z-A)'),
        ('total_amount_desc', 'Amount (High to Low)'),
        ('total_amount_asc', 'Amount (Low to High)'),
        ('movie_title_asc', 'Movie Title (A-Z)'),
        ('movie_title_desc', 'Movie Title (Z-A)')
    ], default='booking_time_desc')
    
    per_page = SelectField('Per Page', choices=[
        (10, '10'),
        (20, '20'),
        (50, '50'),
        (100, '100')
    ], default=20, coerce=int)
    
    # Form actions
    submit = SubmitField('Search')
    save_search = SubmitField('Save Search')
    clear = SubmitField('Clear')
    
    def __init__(self, *args, **kwargs):
        super(AdvancedBookingSearchForm, self).__init__(*args, **kwargs)
        self._populate_show_choices()
    
    def _populate_show_choices(self):
        """Populate show choices with available shows"""
        from app.shows.models import Show
        from app.movies.models import Movie
        
        shows = Show.query.join(Movie).filter(
            Movie.status == 'active',
            Show.show_date >= datetime.now().date() - timedelta(days=30)  # Last 30 days
        ).order_by(Show.show_date.desc(), Show.show_time.desc()).limit(100).all()
        
        self.show_id.choices = [(0, 'All Shows')]
        for show in shows:
            display_text = f"{show.movie.title} - {show.show_date.strftime('%d %b %Y')} at {show.show_time.strftime('%I:%M %p')} - {show.screen.name}"
            self.show_id.choices.append((show.id, display_text))
    
    def validate_search_term(self, field):
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
    
    def validate_customer_email(self, field):
        """Validate customer email"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid email address')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_phone(self, field):
        """Validate customer phone"""
        if field.data:
            # Sanitize phone number
            sanitized = InputSanitizer.sanitize_phone(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid phone number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_seat_number(self, field):
        """Validate seat number format"""
        if field.data:
            # Basic seat number format validation (e.g., "A1", "B12", "C-5")
            seat_pattern = r'^[A-Za-z][0-9\-]+$'
            if not re.match(seat_pattern, field.data.strip()):
                raise ValidationError('Invalid seat number format (e.g., A1, B12, C-5)')
            
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=10)
            field.data = sanitized
    
    def validate_date_range(self):
        """Validate date range"""
        date_from = self.date_from.data
        date_to = self.date_to.data
        
        if date_from and date_to:
            try:
                # Parse dates (assuming YYYY-MM-DD format)
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                if from_date > to_date:
                    raise ValidationError('From date cannot be after to date')
                
                # Limit date range to 1 year
                if (to_date - from_date).days > 365:
                    raise ValidationError('Date range cannot exceed 1 year')
                
            except ValueError:
                raise ValidationError('Invalid date format. Use YYYY-MM-DD format.')
    
    def validate_amount_range(self):
        """Validate amount range"""
        amount_min = self.amount_min.data
        amount_max = self.amount_max.data
        
        if amount_min is not None and amount_max is not None:
            if amount_min > amount_max:
                raise ValidationError('Minimum amount cannot be greater than maximum amount')
    
    def validate_date_format(self):
        """Validate date format"""
        date_fields = [self.date_from, self.date_to]
        
        for field in date_fields:
            if field.data:
                try:
                    datetime.strptime(field.data, '%Y-%m-%d')
                except ValueError:
                    field.errors.append('Invalid date format. Use YYYY-MM-DD format.')