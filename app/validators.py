"""
Centralized Validation Utilities for Cinema Management System
"""
import re
import json
import bleach
from datetime import datetime, time, date, timedelta
from decimal import Decimal, InvalidOperation
from flask import request
from wtforms import ValidationError
from sqlalchemy import and_, or_
from app.database import db


class ValidationError(Exception):
    """Custom validation error for business logic validation"""
    def __init__(self, message, field=None, code=None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class InputSanitizer:
    """Utility class for sanitizing user input"""
    
    @staticmethod
    def sanitize_string(value, allow_tags=None, max_length=None):
        """
        Sanitize string input to prevent XSS attacks
        
        Args:
            value: Input string to sanitize
            allow_tags: List of allowed HTML tags (default: none)
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if value is None:
            return None
            
        # Convert to string if not already
        if not isinstance(value, str):
            value = str(value)
        
        # Strip whitespace
        value = value.strip()
        
        # Truncate if max_length is specified
        if max_length and len(value) > max_length:
            value = value[:max_length]
        
        # Remove HTML tags if not allowed
        if allow_tags is None:
            # Use bleach to strip all HTML tags
            value = bleach.clean(value, tags=[], strip=True)
        else:
            # Allow specific tags
            value = bleach.clean(value, tags=allow_tags, strip=True)
        
        # Remove potentially dangerous characters
        value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
        
        return value
    
    @staticmethod
    def sanitize_email(value):
        """Sanitize email address"""
        if value is None:
            return None
            
        value = str(value).lower().strip()
        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, value):
            return None
            
        return value
    
    @staticmethod
    def sanitize_phone(value, country_code='IN'):
        """Sanitize phone number based on country code"""
        if value is None:
            return None
            
        # Remove all non-digit characters
        digits = re.sub(r'[^\d]', '', str(value))
        
        if country_code == 'IN':
            # Indian phone number validation
            if len(digits) == 10 and digits[0] not in '0':
                return digits
            elif len(digits) == 11 and digits.startswith('0'):
                return digits[1:]
            elif len(digits) == 12 and digits.startswith('91'):
                return digits[2:]
        
        return None
    
    @staticmethod
    def sanitize_numeric(value, min_val=None, max_val=None, decimal_places=None):
        """Sanitize numeric input"""
        if value is None:
            return None
            
        try:
            if decimal_places is not None:
                # Handle decimal values
                if isinstance(value, str):
                    value = value.replace(',', '')
                num = Decimal(str(value))
                # Round to specified decimal places
                quant = Decimal('1').scaleb(-decimal_places)
                num = num.quantize(quant)
            else:
                # Handle integer values
                if isinstance(value, str):
                    value = value.replace(',', '')
                num = Decimal(str(value))
                num = int(num)
            
            # Apply min/max constraints
            if min_val is not None and num < min_val:
                return None
            if max_val is not None and num > max_val:
                return None
                
            return num
            
        except (InvalidOperation, ValueError, TypeError):
            return None


class BusinessValidators:
    """Business logic validators for cinema operations"""
    
    @staticmethod
    def validate_show_scheduling(screen_id, show_date, show_time, show_duration, exclude_show_id=None):
        """
        Validate show scheduling to prevent conflicts
        
        Args:
            screen_id: ID of the screen
            show_date: Date of the show
            show_time: Time of the show
            show_duration: Duration in minutes
            exclude_show_id: ID to exclude (for editing existing shows)
            
        Returns:
            tuple: (is_valid, error_message)
        """
        from app.shows.models import Show
        
        # Calculate end time
        start_datetime = datetime.combine(show_date, show_time)
        end_datetime = start_datetime + datetime.timedelta(minutes=show_duration)
        
        # Build query to check for conflicts
        query = Show.query.filter_by(screen_id=screen_id, show_date=show_date)
        
        # Exclude current show if editing
        if exclude_show_id:
            query = query.filter(Show.id != exclude_show_id)
        
        # Check for overlapping shows
        conflicting_shows = query.filter(
            or_(
                and_(Show.show_time <= show_time, Show.end_time > show_time),
                and_(Show.show_time < end_datetime.time(), Show.end_time >= end_datetime.time()),
                and_(Show.show_time >= show_time, Show.show_time < end_datetime.time())
            )
        ).all()
        
        if conflicting_shows:
            conflict_times = [f"{s.show_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}" 
                            for s in conflicting_shows]
            return False, f"Show conflicts with existing shows: {', '.join(conflict_times)}"
        
        # Validate business hours (6 AM to 11:59 PM)
        if show_time.hour < 6 or end_datetime.time().hour > 23:
            return False, "Show must be scheduled between 6:00 AM and 11:59 PM"
        
        # Validate show is not in the past
        if show_date < datetime.now().date():
            return False, "Show date cannot be in the past"
        
        if show_date == datetime.now().date() and show_time < datetime.now().time():
            return False, "Show time cannot be in the past"
        
        return True, None
    
    @staticmethod
    def validate_seat_availability(show_id, seat_ids):
        """
        Validate seat availability for booking
        
        Args:
            show_id: ID of the show
            seat_ids: List of seat IDs to book
            
        Returns:
            tuple: (is_valid, error_message, available_seats)
        """
        from app.bookings.models import Booking, BookingSeat
        from app.screens.models import Seat
        
        # Check if seat IDs are valid
        seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
        if len(seats) != len(seat_ids):
            invalid_ids = set(seat_ids) - set(s.id for s in seats)
            return False, f"Invalid seat IDs: {', '.join(map(str, invalid_ids))}", []
        
        # Check if seats are already booked
        booked_seats = BookingSeat.query.join(Booking).filter(
            and_(
                Booking.show_id == show_id,
                BookingSeat.seat_id.in_(seat_ids),
                Booking.status.in_(['confirmed', 'pending'])
            )
        ).all()
        
        if booked_seats:
            booked_seat_ids = [bs.seat_id for bs in booked_seats]
            return False, f"Seats already booked: {', '.join(map(str, booked_seat_ids))}", []
        
        # Check maximum seats per booking
        if len(seat_ids) > 10:
            return False, "Cannot book more than 10 seats at once", []
        
        return True, None, seats
    
    @staticmethod
    def validate_payment_amount(amount, booking_amount):
        """
        Validate payment amount against booking amount
        
        Args:
            amount: Payment amount
            booking_amount: Required booking amount
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            payment_amount = Decimal(str(amount))
            required_amount = Decimal(str(booking_amount))
            
            if payment_amount <= 0:
                return False, "Payment amount must be positive"
            
            if payment_amount < required_amount:
                return False, f"Payment amount (₹{payment_amount}) is less than required amount (₹{required_amount})"
            
            if payment_amount > required_amount * Decimal('1.1'):  # Allow 10% tolerance
                return False, f"Payment amount (₹{payment_amount}) exceeds reasonable amount (₹{required_amount})"
            
            return True, None
            
        except (InvalidOperation, ValueError, TypeError):
            return False, "Invalid payment amount format"
    
    @staticmethod
    def validate_refund_eligibility(payment, refund_amount):
        """
        Validate if a payment is eligible for refund
        
        Args:
            payment: Payment object
            refund_amount: Amount to refund
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Check payment status
            if payment.status != 'completed':
                return False, "Only completed payments can be refunded"
            
            # Check refund amount
            refund_decimal = Decimal(str(refund_amount))
            payment_amount = Decimal(str(payment.amount))
            
            if refund_decimal <= 0:
                return False, "Refund amount must be positive"
            
            if refund_decimal > payment_amount:
                return False, "Refund amount cannot exceed payment amount"
            
            # Check if show has already started
            if payment.booking and payment.booking.show:
                show_datetime = datetime.combine(
                    payment.booking.show.show_date, 
                    payment.booking.show.show_time
                )
                if show_datetime < datetime.now():
                    return False, "Cannot refund tickets for shows that have already started"
            
            return True, None
            
        except (InvalidOperation, ValueError, TypeError):
            return False, "Invalid refund amount format"


class DataValidators:
    """Data format and integrity validators"""
    
    @staticmethod
    def validate_username_format(username):
        """
        Validate username format according to requirements
        
        Args:
            username: Username string to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not username:
            return False
        
        # Username should be 3-30 characters long
        if len(username) < 3 or len(username) > 30:
            return False
        
        # Username should contain only alphanumeric characters and underscores
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return False
        
        # Username should not start or end with underscore
        if username.startswith('_') or username.endswith('_'):
            return False
        
        return True
    
    @staticmethod
    def validate_email_format(email):
        """
        Validate email format
        
        Args:
            email: Email string to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not email:
            return False
        
        # Basic email format validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    @staticmethod
    def validate_password_strength(password):
        """
        Validate password strength according to security requirements
        
        Args:
            password: Password string to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"
        
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if len(password) > 128:
            return False, "Password cannot exceed 128 characters"
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, None
    
    @staticmethod
    def validate_card_number(card_number):
        """
        Validate credit card number using Luhn algorithm
        
        Args:
            card_number: Card number string
            
        Returns:
            tuple: (is_valid, error_message, card_type)
        """
        # Remove spaces and dashes
        clean_number = re.sub(r'[\s-]', '', str(card_number))
        
        # Check if it contains only digits
        if not clean_number.isdigit():
            return False, "Card number must contain only digits", None
        
        # Check length
        if len(clean_number) < 13 or len(clean_number) > 19:
            return False, "Card number must be 13-19 digits long", None
        
        # Luhn algorithm
        total = 0
        reverse_digits = clean_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:  # Every second digit
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        if total % 10 != 0:
            return False, "Invalid card number", None
        
        # Determine card type
        card_type = None
        if clean_number.startswith('4'):
            card_type = 'visa'
        elif clean_number.startswith('5') or clean_number.startswith('2'):
            card_type = 'mastercard'
        elif clean_number.startswith('3') and len(clean_number) == 15:
            card_type = 'amex'
        elif clean_number.startswith('6'):
            card_type = 'discover'
        else:
            card_type = 'other'
        
        return True, None, card_type
    
    @staticmethod
    def validate_upi_id(upi_id):
        """Validate UPI ID format"""
        if not upi_id:
            return False, "UPI ID is required"
        
        upi_pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
        if not re.match(upi_pattern, upi_id):
            return False, "Invalid UPI ID format. Expected format: username@provider"
        
        return True, None
    
    @staticmethod
    def validate_date_range(start_date, end_date, max_days=365):
        """
        Validate date range for reports and filters
        
        Args:
            start_date: Start date
            end_date: End date
            max_days: Maximum allowed days between dates
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if start_date and end_date:
            if start_date > end_date:
                return False, "Start date cannot be after end date"
            
            days_diff = (end_date - start_date).days
            if days_diff > max_days:
                return False, f"Date range cannot exceed {max_days} days"
        
        return True, None
    
    @staticmethod
    def validate_file_upload(file_obj, allowed_extensions=None, max_size_mb=5):
        """
        Validate uploaded file
        
        Args:
            file_obj: File object from request
            allowed_extensions: List of allowed file extensions
            max_size_mb: Maximum file size in MB
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not file_obj or file_obj.filename == '':
            return False, "No file selected"
        
        # Check file extension
        if allowed_extensions:
            filename = file_obj.filename.lower()
            allowed = any(filename.endswith(f'.{ext.lower()}') for ext in allowed_extensions)
            if not allowed:
                return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        # Check file size
        file_obj.seek(0, 2)  # Seek to end
        file_size = file_obj.tell()
        file_obj.seek(0)  # Reset to beginning
        
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return False, f"File size exceeds maximum allowed size of {max_size_mb}MB"
        
        return True, None


class CrossFieldValidators:
    """Validators that check relationships between multiple fields"""
    
    @staticmethod
    def validate_password_confirmation(password, confirmation):
        """Validate password confirmation matches"""
        if password != confirmation:
            return False, "Passwords do not match"
        return True, None
    
    @staticmethod
    def validate_show_time_conflict(show_date, show_time, end_time, existing_show=None):
        """Validate show time doesn't conflict with existing shows"""
        if not all([show_date, show_time, end_time]):
            return False, "Show date, time, and end time are required"
        
        # Convert to time objects for comparison
        if isinstance(show_time, str):
            show_time = datetime.strptime(show_time, '%H:%M').time()
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%H:%M').time()
        
        # Basic time validation
        if show_time >= end_time:
            return False, "Show start time must be before end time"
        
        # Validate business hours
        if show_time.hour < 6 or end_time.hour > 23 or (end_time.hour == 23 and end_time.minute > 59):
            return False, "Show must be scheduled between 6:00 AM and 11:59 PM"
        
        return True, None
    
    @staticmethod
    def validate_seat_layout(layout_definition, total_rows, total_columns):
        """
        Validate custom seat layout definition
        
        Args:
            layout_definition: String defining seat layout
            total_rows: Total rows in screen
            total_columns: Total columns in screen
            
        Returns:
            tuple: (is_valid, error_message, parsed_layout)
        """
        if not layout_definition:
            return False, "Layout definition is required", None
        
        lines = layout_definition.strip().split('\n')
        parsed_layout = {}
        
        # Expected format: A:NNNPPV (row:seat_pattern)
        valid_seat_types = {'N': 'normal', 'P': 'premium', 'V': 'vip', 'E': 'empty'}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if ':' not in line:
                return False, f"Invalid line format: {line}. Expected format: ROW:PATTERN", None
            
            row_part, pattern_part = line.split(':', 1)
            row = row_part.strip().upper()
            pattern = pattern_part.strip().upper()
            
            # Validate row letter
            if len(row) != 1 or not row.isalpha():
                return False, f"Invalid row identifier: {row}. Must be a single letter", None
            
            # Validate pattern length
            if len(pattern) != total_columns:
                return False, f"Pattern length ({len(pattern)}) must match screen columns ({total_columns})", None
            
            # Validate pattern characters
            for char in pattern:
                if char not in valid_seat_types:
                    return False, f"Invalid seat type '{char}' in pattern. Valid types: {', '.join(valid_seat_types.keys())}", None
            
            parsed_layout[row] = pattern
        
        # Validate row count
        if len(parsed_layout) != total_rows:
            return False, f"Layout must define exactly {total_rows} rows", None
        
        return True, None, parsed_layout


# Custom WTForms validators
def validate_seat_availability(show_id_field='show_id', seat_ids_field='selected_seats'):
    """Custom validator for seat availability in forms"""
    def validator(form, field):
        if not hasattr(form, show_id_field) or not getattr(form, show_id_field).data:
            raise ValidationError("Show ID is required")
        
        if field.name == seat_ids_field and not field.data:
            raise ValidationError("Please select at least one seat")
        
        if field.name == seat_ids_field and field.data:
            # Parse seat IDs
            seat_ids = [int(s.strip()) for s in field.data.split(',') if s.strip()]
            
            # Validate availability
            is_valid, error_message, seats = BusinessValidators.validate_seat_availability(
                getattr(form, show_id_field).data, seat_ids
            )
            
            if not is_valid:
                raise ValidationError(error_message)
    
    return validator


def validate_show_time_conflict(show_id_field=None):
    """Custom validator for show time conflicts"""
    def validator(form, field):
        # This would be used in show forms to prevent scheduling conflicts
        # Implementation would depend on form structure
        pass
    
    return validator


# Security validation helpers
class SecurityValidator:
    """Security-focused validation utilities"""
    
    @staticmethod
    def detect_sql_injection(input_string):
        """
        Detect potential SQL injection attempts
        
        Args:
            input_string: String or list to check
            
        Returns:
            bool: True if potential injection detected
        """
        if not input_string:
            return False
        
        # Handle list input by joining all elements
        if isinstance(input_string, list):
            input_string = ' '.join(str(item) for item in input_string)
        
        # Convert to string if not already
        if not isinstance(input_string, str):
            input_string = str(input_string)
        
        # Common SQL injection patterns
        sql_patterns = [
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bSELECT\b.*\bFROM\b)",
            r"(\bINSERT\b.*\bINTO\b)",
            r"(\bUPDATE\b.*\bSET\b)",
            r"(\bDELETE\b.*\bFROM\b)",
            r"(\bDROP\b.*\bTABLE\b)",
            r"(\bCREATE\b.*\bTABLE\b)",
            r"(\bALTER\b.*\bTABLE\b)",
            r"(--|/\*|\*/|#)",
            r"(\bOR\b.*=.*\bOR\b)",
            r"(\bAND\b.*=.*\bAND\b)",
            r"('\s*=\s*'.*|\".*=.*\")",
            r"(\bxp_cmdshell\b)",
            r"(\bexec\b.*\bxp_cmdshell\b)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def detect_xss(input_string):
        """
        Detect potential XSS attempts
        
        Args:
            input_string: String to check
            
        Returns:
            bool: True if potential XSS detected
        """
        if not input_string:
            return False
        
        # Common XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"eval\s*\(",
            r"expression\s*\(",
            r"@import",
            r"<style[^>]*>.*?</style>"
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_string, re.IGNORECASE | re.DOTALL):
                return True
        
        return False
    
    @staticmethod
    def validate_csrf_token():
        """Validate CSRF token in current request"""
        # This would integrate with Flask-WTF's CSRF protection
        # Implementation depends on specific requirements
        return True
    
    @staticmethod
    def is_suspicious_pattern(input_string):
        """
        Detect suspicious patterns in input strings
        
        Args:
            input_string: String to check for suspicious patterns
            
        Returns:
            bool: True if suspicious pattern detected
        """
        if not input_string:
            return False
        
        # Convert to string if not already
        if not isinstance(input_string, str):
            input_string = str(input_string)
        
        # Common suspicious patterns
        suspicious_patterns = [
            r'\b(admin|administrator|root|superuser)\b.*\b(login|signin|auth)\b',
            r'\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(from|into|table)\b',
            r'\b(script|javascript|vbscript|onload|onerror)\b',
            r'\b(eval|exec|system|shell)\b',
            r'\b(\.\./|\.\.\\)\b',  # Directory traversal
            r'[<>]',  # HTML tags
            r'[\'"]\s*[=;]',  # Potential injection
            r'\b(and|or)\s+[\d\w]+\s*[=<>!]',  # SQL injection pattern
            r'\b(waitfor|delay|sleep)\b',  # Time-based attacks
            r'\b(xp_|sp_)\w+',  # SQL stored procedures
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return True
        
        return False