"""
Enhanced Validation Utilities for Cinema Management System
"""
import re
import json
import bleach
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from flask import request
from wtforms import ValidationError
from sqlalchemy import and_, or_
from app.database import db


class AsyncValidators:
    """Asynchronous validators for real-time validation"""
    
    @staticmethod
    async def validate_username_availability(username, exclude_user_id=None):
        """
        Validate username availability asynchronously
        
        Args:
            username: Username to check
            exclude_user_id: User ID to exclude (for editing)
            
        Returns:
            dict: Validation result with availability status
        """
        try:
            from app.auth.models import User
            
            query = User.query.filter_by(username=username)
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)
            
            existing_user = query.first()
            
            return {
                'valid': True,
                'available': existing_user is None,
                'message': 'Username is available' if existing_user is None else 'Username is already taken'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'available': False,
                'message': f'Error checking username availability: {str(e)}'
            }
    
    @staticmethod
    async def validate_email_availability(email, exclude_user_id=None):
        """
        Validate email availability asynchronously
        
        Args:
            email: Email to check
            exclude_user_id: User ID to exclude (for editing)
            
        Returns:
            dict: Validation result with availability status
        """
        try:
            from app.auth.models import User
            
            query = User.query.filter_by(email=email)
            if exclude_user_id:
                query = query.filter(User.id != exclude_user_id)
            
            existing_user = query.first()
            
            return {
                'valid': True,
                'available': existing_user is None,
                'message': 'Email is available' if existing_user is None else 'Email is already registered'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'available': False,
                'message': f'Error checking email availability: {str(e)}'
            }
    
    @staticmethod
    async def validate_show_seat_availability(show_id, seat_ids, exclude_booking_id=None):
        """
        Validate seat availability for a show asynchronously
        
        Args:
            show_id: ID of the show
            seat_ids: List of seat IDs to validate
            exclude_booking_id: Booking ID to exclude (for editing)
            
        Returns:
            dict: Validation result with seat availability status
        """
        try:
            from app.bookings.models import Booking, BookingSeat
            from app.screens.models import Seat
            
            # Validate seat IDs exist
            seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
            if len(seats) != len(seat_ids):
                invalid_ids = set(seat_ids) - set(s.id for s in seats)
                return {
                    'valid': False,
                    'message': f'Invalid seat IDs: {", ".join(map(str, invalid_ids))}'
                }
            
            # Check seat availability
            query = BookingSeat.query.join(Booking).filter(
                Booking.show_id == show_id,
                BookingSeat.seat_id.in_(seat_ids),
                Booking.status.in_(['confirmed', 'pending'])
            )
            
            if exclude_booking_id:
                query = query.filter(Booking.id != exclude_booking_id)
            
            booked_seats = query.all()
            
            if booked_seats:
                booked_seat_ids = [bs.seat_id for bs in booked_seats]
                available_seats = [sid for sid in seat_ids if sid not in booked_seat_ids]
                
                return {
                    'valid': False,
                    'available_seats': available_seats,
                    'booked_seats': booked_seat_ids,
                    'message': f'Seats {", ".join(map(str, booked_seat_ids))} are already booked'
                }
            
            return {
                'valid': True,
                'available_seats': seat_ids,
                'booked_seats': [],
                'message': 'All seats are available'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'message': f'Error checking seat availability: {str(e)}'
            }


class BusinessRuleValidators:
    """Enhanced business rule validators"""
    
    @staticmethod
    def validate_booking_time_restrictions(show_id, user_id=None):
        """
        Validate booking time restrictions
        
        Args:
            show_id: ID of the show
            user_id: ID of the user (optional)
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            from app.shows.models import Show
            from datetime import datetime, timedelta
            
            show = Show.query.get(show_id)
            if not show:
                return False, "Show not found"
            
            now = datetime.utcnow()
            show_datetime = datetime.combine(show.show_date, show.show_time)
            
            # Check if show is in the past
            if show_datetime < now:
                return False, "Cannot book shows that have already started"
            
            # Check if show is too far in future (more than 30 days)
            if show_datetime > now + timedelta(days=30):
                return False, "Cannot book shows more than 30 days in advance"
            
            # Check if show is within booking window (e.g., no bookings within 2 hours of show time)
            booking_window = timedelta(hours=2)
            if show_datetime - now < booking_window:
                return False, "Bookings must be made at least 2 hours before show time"
            
            # Check user-specific restrictions
            if user_id:
                from app.auth.models import User
                user = User.query.get(user_id)
                if user and user.role == 'cashier':
                    # Cashiers might have additional restrictions
                    if show_datetime > now + timedelta(days=7):
                        return False, "Cashiers can only book shows up to 7 days in advance"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating booking time: {str(e)}"
    
    @staticmethod
    def validate_pricing_rules(show_id, seat_ids, proposed_price):
        """
        Validate pricing against business rules
        
        Args:
            show_id: ID of the show
            seat_ids: List of seat IDs
            proposed_price: Proposed total price
            
        Returns:
            tuple: (is_valid, error_message, calculated_price)
        """
        try:
            from app.shows.models import Show
            from app.screens.models import Seat
            from decimal import Decimal, InvalidOperation
            
            show = Show.query.get(show_id)
            if not show:
                return False, "Show not found", None
            
            # Get seats and calculate expected price
            seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
            if len(seats) != len(seat_ids):
                return False, "Invalid seat IDs", None
            
            base_price = Decimal(str(show.base_price or 0))
            total_price = Decimal('0')
            
            for seat in seats:
                seat_price = base_price
                
                # Apply seat type multipliers
                if seat.type == 'premium':
                    seat_price *= Decimal('1.5')
                elif seat.type == 'vip':
                    seat_price *= Decimal('2.0')
                
                # Apply show-specific adjustments
                if show.weekend_surcharge and show.show_date.weekday() >= 5:
                    seat_price *= (Decimal('1') + Decimal(str(show.weekend_surcharge)) / Decimal('100'))
                
                if show.matinee_discount and show.show_time.hour < 17:
                    seat_price *= (Decimal('1') - Decimal(str(show.matinee_discount)) / Decimal('100'))
                
                total_price += seat_price
            
            # Validate proposed price matches calculated price (with small tolerance)
            try:
                proposed_decimal = Decimal(str(proposed_price))
                tolerance = Decimal('0.01')  # 1 paise tolerance
                
                if abs(proposed_decimal - total_price) > tolerance:
                    return False, f"Price mismatch. Expected: ₹{total_price}, Proposed: ₹{proposed_price}", total_price
            except InvalidOperation:
                return False, "Invalid price format", total_price
            
            # Check minimum and maximum price limits
            min_price_per_seat = Decimal('50')  # Minimum ₹50 per seat
            if len(seats) > 0 and total_price / len(seats) < min_price_per_seat:
                return False, f"Price too low. Minimum ₹{min_price_per_seat} per seat", total_price
            
            max_total_price = Decimal('50000')  # Maximum ₹50,000 per booking
            if total_price > max_total_price:
                return False, f"Total price exceeds maximum allowed amount of ₹{max_total_price}", total_price
            
            return True, None, total_price
            
        except Exception as e:
            return False, f"Error validating pricing: {str(e)}", None
    
    @staticmethod
    def validate_payment_method_limits(user_id, payment_method, amount):
        """
        Validate payment method limits and restrictions
        
        Args:
            user_id: ID of the user
            payment_method: Payment method
            amount: Payment amount
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            from app.auth.models import User
            from decimal import Decimal
            
            # Get user information
            user = User.query.get(user_id) if user_id else None
            
            # Define payment method limits
            payment_limits = {
                'cash': {'max_per_transaction': Decimal('100000'), 'max_daily': Decimal('500000')},
                'card': {'max_per_transaction': Decimal('200000'), 'max_daily': Decimal('1000000')},
                'upi': {'max_per_transaction': Decimal('100000'), 'max_daily': Decimal('500000')},
                'wallet': {'max_per_transaction': Decimal('50000'), 'max_daily': Decimal('200000')},
                'netbanking': {'max_per_transaction': Decimal('500000'), 'max_daily': Decimal('2000000')}
            }
            
            if payment_method not in payment_limits:
                return False, "Invalid payment method"
            
            limits = payment_limits[payment_method]
            amount_decimal = Decimal(str(amount))
            
            # Check per-transaction limit
            if amount_decimal > limits['max_per_transaction']:
                return False, f"Amount exceeds maximum allowed for {payment_method}: ₹{limits['max_per_transaction']}"
            
            # Check daily limit (simplified - in real implementation, would check today's transactions)
            # This would need to be enhanced with actual daily transaction tracking
            
            # Additional restrictions for cashiers
            if user and user.role == 'cashier':
                if payment_method == 'cash' and amount_decimal > Decimal('50000'):
                    return False, "Cashiers can only process cash payments up to ₹50,000"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating payment method: {str(e)}"


class DatabaseConstraintValidators:
    """Database constraint validators"""
    
    @staticmethod
    def validate_referential_integrity(model_class, record_id, related_field, related_value):
        """
        Validate referential integrity before database operations
        
        Args:
            model_class: SQLAlchemy model class
            record_id: ID of the record being validated
            related_field: Field name that references another table
            related_value: Value being referenced
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            from app.database import db
            
            # Check if related record exists
            related_model_class = getattr(model_class, related_field).property.mapper.class_
            related_record = related_model_class.query.get(related_value)
            
            if not related_record:
                return False, f"Referenced {related_model_class.__name__} record does not exist"
            
            # Check for circular references
            if hasattr(related_model_class, related_field):
                # This would need to be enhanced based on specific relationships
                pass
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating referential integrity: {str(e)}"
    
    @staticmethod
    def validate_unique_constraint(model_class, field_name, field_value, exclude_id=None):
        """
        Validate unique constraint before database operations
        
        Args:
            model_class: SQLAlchemy model class
            field_name: Name of the field with unique constraint
            field_value: Value to check for uniqueness
            exclude_id: ID to exclude from uniqueness check (for updates)
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            query = model_class.query.filter(getattr(model_class, field_name) == field_value)
            
            if exclude_id:
                query = query.filter(model_class.id != exclude_id)
            
            existing_record = query.first()
            
            if existing_record:
                return False, f"{field_name} '{field_value}' already exists"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating unique constraint: {str(e)}"
    
    @staticmethod
    def validate_business_rules_before_save(model_instance):
        """
        Validate business rules before saving to database
        
        Args:
            model_instance: SQLAlchemy model instance
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Get model class for type-specific validation
            model_class = model_instance.__class__.__name__
            
            if model_class == 'Show':
                return DatabaseConstraintValidators._validate_show_business_rules(model_instance)
            elif model_class == 'Booking':
                return DatabaseConstraintValidators._validate_booking_business_rules(model_instance)
            elif model_class == 'Payment':
                return DatabaseConstraintValidators._validate_payment_business_rules(model_instance)
            elif model_class == 'Movie':
                return DatabaseConstraintValidators._validate_movie_business_rules(model_instance)
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating business rules: {str(e)}"
    
    @staticmethod
    def _validate_show_business_rules(show_instance):
        """Validate show-specific business rules"""
        from datetime import datetime, time, timedelta
        
        # Check show time is within business hours
        if show_instance.show_time:
            hour = show_instance.show_time.hour
            if hour < 6 or hour > 23:
                return False, "Show time must be between 6:00 AM and 11:59 PM"
        
        # Check show date is not too far in future
        if show_instance.show_date:
            max_future_date = datetime.now().date() + timedelta(days=90)
            if show_instance.show_date > max_future_date:
                return False, "Shows cannot be scheduled more than 90 days in advance"
        
        # Check show date is not in past
        if show_instance.show_date:
            min_past_date = datetime.now().date() - timedelta(days=1)
            if show_instance.show_date < min_past_date:
                return False, "Shows cannot be scheduled in the past"
        
        return True, None
    
    @staticmethod
    def _validate_booking_business_rules(booking_instance):
        """Validate booking-specific business rules"""
        from datetime import datetime, timedelta
        
        # Check maximum seats per booking
        if hasattr(booking_instance, 'seats'):
            seat_count = len(booking_instance.seats) if booking_instance.seats else 0
            if seat_count > 10:
                return False, "Maximum 10 seats allowed per booking"
        
        # Check booking is not too far in future
        if booking_instance.booking_time:
            max_future_booking = datetime.now() + timedelta(days=30)
            if booking_instance.booking_time > max_future_booking:
                return False, "Bookings cannot be made more than 30 days in advance"
        
        return True, None
    
    @staticmethod
    def _validate_payment_business_rules(payment_instance):
        """Validate payment-specific business rules"""
        from decimal import Decimal
        
        # Check payment amount is positive
        if payment_instance.amount:
            try:
                amount = Decimal(str(payment_instance.amount))
                if amount <= 0:
                    return False, "Payment amount must be positive"
                
                # Check maximum payment amount
                max_amount = Decimal('100000')  # ₹1 lakh
                if amount > max_amount:
                    return False, f"Payment amount cannot exceed ₹{max_amount}"
            except:
                return False, "Invalid payment amount format"
        
        return True, None
    
    @staticmethod
    def _validate_movie_business_rules(movie_instance):
        """Validate movie-specific business rules"""
        from datetime import datetime, timedelta
        
        # Check release date is reasonable
        if movie_instance.release_date:
            # Release date should not be more than 2 years in future
            max_future_release = datetime.now().date() + timedelta(days=730)
            if movie_instance.release_date > max_future_release:
                return False, "Release date cannot be more than 2 years in future"
            
            # Release date should not be more than 50 years in past
            min_past_release = datetime.now().date() - timedelta(days=18250)
            if movie_instance.release_date < min_past_release:
                return False, "Release date seems too far in the past"
        
        return True, None


class RealTimeValidationManager:
    """Manager for real-time validation operations"""
    
    def __init__(self):
        self.validation_cache = {}
        self.cache_timeout = 300  # 5 minutes
    
    def get_cached_result(self, validation_key):
        """Get cached validation result"""
        if validation_key in self.validation_cache:
            result, timestamp = self.validation_cache[validation_key]
            if datetime.utcnow().timestamp() - timestamp < self.cache_timeout:
                return result
        return None
    
    def set_cached_result(self, validation_key, result):
        """Set cached validation result"""
        self.validation_cache[validation_key] = (
            result, 
            datetime.utcnow().timestamp()
        )
    
    def clear_cache(self):
        """Clear validation cache"""
        self.validation_cache.clear()
    
    async def validate_field_async(self, field_name, field_value, validation_type, **kwargs):
        """Perform asynchronous field validation"""
        validation_key = f"{validation_type}:{field_name}:{field_value}"
        
        # Check cache first
        cached_result = self.get_cached_result(validation_key)
        if cached_result:
            return cached_result
        
        # Perform validation based on type
        if validation_type == 'username_availability':
            result = await AsyncValidators.validate_username_availability(
                field_value, 
                kwargs.get('exclude_user_id')
            )
        elif validation_type == 'email_availability':
            result = await AsyncValidators.validate_email_availability(
                field_value, 
                kwargs.get('exclude_user_id')
            )
        elif validation_type == 'seat_availability':
            result = await AsyncValidators.validate_show_seat_availability(
                kwargs.get('show_id'),
                field_value,  # field_value should be list of seat IDs
                kwargs.get('exclude_booking_id')
            )
        else:
            result = {
                'valid': False,
                'message': f'Unknown validation type: {validation_type}'
            }
        
        # Cache the result
        self.set_cached_result(validation_key, result)
        
        return result


class ValidationAuditor:
    """Audit logging for validation failures and successes"""
    
    @staticmethod
    def log_validation_attempt(field_name, field_value, validation_result, context=None):
        """
        Log validation attempts for auditing
        
        Args:
            field_name: Name of the field being validated
            field_value: Value being validated
            validation_result: Result of validation (dict with valid, message, etc.)
            context: Additional context (user_id, form_name, etc.)
        """
        try:
            from app.error_handlers import ErrorLogger
            
            audit_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'field_name': field_name,
                'field_value': str(field_value)[:100],  # Limit value length for privacy
                'validation_result': validation_result,
                'context': context or {},
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'ip_address': request.remote_addr
            }
            
            if validation_result.get('valid'):
                ErrorLogger.log_info('Validation Success', audit_data)
            else:
                ErrorLogger.log_warning('Validation Failure', audit_data)
                
        except Exception as e:
            # Fallback logging if audit logging fails
            import logging
            logging.error(f"Failed to log validation audit: {str(e)}")
    
    @staticmethod
    def log_security_violation(violation_type, details, severity='medium'):
        """
        Log security violations for monitoring
        
        Args:
            violation_type: Type of security violation
            details: Details of the violation
            severity: Severity level (low, medium, high, critical)
        """
        try:
            from app.error_handlers import ErrorLogger
            
            audit_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'violation_type': violation_type,
                'details': details,
                'severity': severity,
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'ip_address': request.remote_addr,
                'user_id': getattr(request, 'current_user', None) and hasattr(request.current_user, 'id') and request.current_user.id
            }
            
            ErrorLogger.log_security_event(violation_type, details, severity=severity)
            
        except Exception as e:
            # Fallback logging if audit logging fails
            import logging
            logging.error(f"Failed to log security violation: {str(e)}")


# Enhanced custom WTForms validators
def validate_unique_field(model_class, field_name, exclude_id=None):
    """Custom validator for unique field constraints"""
    def validator(form, field):
        if field.data:
            is_valid, error_message = DatabaseConstraintValidators.validate_unique_constraint(
                model_class, field_name, field.data, exclude_id
            )
            
            if not is_valid:
                raise ValidationError(error_message)
    
    return validator


def validate_business_rules(model_type):
    """Custom validator for business rules"""
    def validator(form, field):
        if field.data:
            is_valid, error_message = DatabaseConstraintValidators.validate_business_rules_before_save(
                field.data
            )
            
            if not is_valid:
                raise ValidationError(error_message)
    
    return validator


def validate_async_field(validation_type, **kwargs):
    """Custom validator for asynchronous field validation"""
    def validator(form, field):
        if field.data:
            # This would typically be called server-side
            # Real async validation would happen via AJAX
            # For now, just basic validation
            if validation_type == 'username' and len(field.data) < 3:
                raise ValidationError('Username must be at least 3 characters long')
            elif validation_type == 'email' and '@' not in field.data:
                raise ValidationError('Invalid email format')
    
    return validator