"""
Centralized Error Handling System for Cinema Management System
"""
import logging
import traceback
from datetime import datetime
from flask import current_app, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from app.database import db
from app.validators import ValidationError, SecurityValidator
from app.enhanced_validators import ValidationAuditor


# Configure error logging
error_logger = logging.getLogger('cinema_errors')
error_logger.setLevel(logging.ERROR)

# Create file handler for error logs
file_handler = logging.FileHandler('logs/errors.log')
file_handler.setLevel(logging.ERROR)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
)
file_handler.setFormatter(formatter)

# Add handler to logger
error_logger.addHandler(file_handler)


class ErrorContext:
    """Context for storing error information"""
    def __init__(self, error=None, user_id=None, request_data=None):
        self.timestamp = datetime.utcnow()
        self.error = error
        self.user_id = user_id or (current_user.id if current_user.is_authenticated else None)
        self.request_data = request_data or self._get_request_data()
        self.ip_address = request.remote_addr
        self.user_agent = request.headers.get('User-Agent', 'Unknown')
        self.url = request.url
        self.method = request.method
        self.traceback = traceback.format_exc() if error else None
    
    def _get_request_data(self):
        """Extract relevant request data for logging"""
        data = {
            'form_data': dict(request.form) if request.form else {},
            'query_args': dict(request.args) if request.args else {},
        }
        
        # Remove sensitive data from logs
        sensitive_fields = ['password', 'password2', 'current_password', 'cvv', 
                          'card_number', 'card_holder', 'paypal_order_id']
        
        for field in sensitive_fields:
            if field in data['form_data']:
                data['form_data'][field] = '[REDACTED]'
        
        return data
    
    def to_dict(self):
        """Convert error context to dictionary for logging"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'error': str(self.error) if self.error else None,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'url': self.url,
            'method': self.method,
            'request_data': self.request_data,
            'traceback': self.traceback
        }


class ErrorLogger:
    """Centralized error logging utility"""
    
    @staticmethod
    def log_error(error, context=None, severity='error', **kwargs):
        """
        Log error with context information
        
        Args:
            error: Exception or error message
            context: Additional context information (can be dict, ErrorContext, or None)
            severity: Log level (error, warning, info)
            **kwargs: Additional context information
        """
        # Create error context if not provided
        if context is None:
            context = ErrorContext(error)
        
        # Get base log data from context
        if isinstance(context, ErrorContext):
            log_data = context.to_dict()
        else:
            log_data = {'timestamp': datetime.utcnow().isoformat()}
        
        # Add additional context if provided
        if isinstance(context, dict):
            log_data.update(context)
        elif kwargs:
            log_data.update(kwargs)
        
        # Log to file
        if severity == 'error':
            error_logger.error(f"Error: {log_data}")
        elif severity == 'warning':
            error_logger.warning(f"Warning: {log_data}")
        else:
            error_logger.info(f"Info: {log_data}")
        
        # Log to application logger
        current_app.logger.error(f"Error occurred: {error}")
    
    @staticmethod
    def log_security_event(event_type, details, request=None, severity='warning', **kwargs):
        """
        Log security-related events
        
        Args:
            event_type: Type of security event
            details: Event details
            request: Flask request object (optional)
            severity: Log level
            **kwargs: Additional context information (user_id, session_data, context, etc.)
        """
        # Create error context if request is provided
        if request:
            context = ErrorContext()
        else:
            context = None
        
        log_data = {
            'security_event': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details,
            'user_id': kwargs.get('user_id') or (context.user_id if context else None),
            'ip_address': context.ip_address if context else None,
            'user_agent': context.user_agent if context else None,
            'url': context.url if context else None
        }
        
        # Add any additional context from kwargs
        log_data.update(kwargs)
        
        if severity == 'error':
            error_logger.error(f"Security Event: {log_data}")
        else:
            error_logger.warning(f"Security Event: {log_data}")
    
    @staticmethod
    def log_validation_error(field, value, error_message, form_name=None):
        """
        Log validation errors for monitoring
        
        Args:
            field: Field name that failed validation
            value: Value that failed validation
            error_message: Validation error message
            form_name: Name of the form
        """
        context = ErrorContext()
        log_data = {
            'validation_error': True,
            'timestamp': datetime.utcnow().isoformat(),
            'field': field,
            'value': str(value)[:100],  # Limit value length
            'error_message': error_message,
            'form_name': form_name,
            'user_id': context.user_id,
            'ip_address': context.ip_address
        }
        
        error_logger.warning(f"Validation Error: {log_data}")


class ErrorRenderer:
    """Handles rendering of error pages and responses"""
    
    @staticmethod
    def render_error_page(error_code, error_message=None, error_details=None):
        """
        Render appropriate error page
        
        Args:
            error_code: HTTP error code
            error_message: Custom error message
            error_details: Additional error details
        """
        # Prepare error context
        error_context = {
            'error_code': error_code,
            'error_message': error_message,
            'error_details': error_details,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': current_user.id if current_user.is_authenticated else None
        }
        
        # Log the error
        ErrorLogger.log_error(error_message or f"HTTP {error_code}", error_context)
        
        # Choose template based on error code
        template_map = {
            400: 'errors/400.html',
            401: 'errors/401.html',
            403: 'errors/403.html',
            404: 'errors/404.html',
            429: 'errors/429.html',
            500: 'errors/500.html',
            502: 'errors/502.html',
            503: 'errors/503.html'
        }
        
        template = template_map.get(error_code, 'errors/500.html')
        
        try:
            return render_template(template, **error_context), error_code
        except Exception as e:
            # Fallback to simple error page if template fails
            return f"<h1>Error {error_code}</h1><p>{error_message or 'An error occurred'}</p>", error_code
    
    @staticmethod
    def render_json_error(error_code, error_message, error_details=None):
        """
        Render JSON error response for API endpoints
        
        Args:
            error_code: HTTP error code
            error_message: Error message
            error_details: Additional error details
        """
        response_data = {
            'success': False,
            'error': {
                'code': error_code,
                'message': error_message,
                'details': error_details
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add user info if authenticated
        if current_user.is_authenticated:
            response_data['user_id'] = current_user.id
        
        # Log the error
        ErrorLogger.log_error(error_message, **{
            'api_error': True,
            'error_code': error_code,
            'response_data': response_data
        })
        
        return jsonify(response_data), error_code


class ErrorHandler:
    """Main error handling class with specific handlers for different error types"""
    
    @staticmethod
    def handle_error(error, request, is_json=False):
        """
        Handle general errors
        
        Args:
            error: Exception instance
            request: Flask request object
            is_json: Whether to return JSON response
        """
        # Log the error
        ErrorLogger.log_error(error)
        
        # Determine error type and handle accordingly
        if isinstance(error, ValidationError):
            return ErrorHandler.handle_validation_error(error, is_json)
        elif isinstance(error, SQLAlchemyError):
            return ErrorHandler.handle_database_error(error, is_json)
        else:
            # Handle general exceptions
            error_message = str(error) if error else "An unexpected error occurred"
            
            if is_json:
                return ErrorRenderer.render_json_error(500, error_message, {'general_error': True})
            else:
                flash(error_message, 'danger')
                return redirect(request.referrer or url_for('index'))
    
    @staticmethod
    def handle_validation_error(error, is_json=False):
        """
        Handle validation errors from forms and business logic
        
        Args:
            error: ValidationError instance
            is_json: Whether to return JSON response
        """
        # Enhanced logging with ValidationAuditor
        ValidationAuditor.log_validation_attempt(
            getattr(error, 'field', 'unknown'),
            getattr(error, 'value', 'unknown'),
            {'valid': False, 'message': error.message},
            {'form_name': getattr(error, 'form_name', None)}
        )
        
        # Legacy logging for compatibility
        ErrorLogger.log_validation_error(
            getattr(error, 'field', 'unknown'),
            getattr(error, 'value', 'unknown'),
            error.message,
            getattr(error, 'form_name', None)
        )
        
        if is_json:
            return ErrorRenderer.render_json_error(
                400,
                error.message,
                {'field': getattr(error, 'field', None), 'code': getattr(error, 'code', None)}
            )
        else:
            flash(error.message, 'danger')
            return redirect(request.referrer or url_for('index'))
    
    @staticmethod
    def handle_database_error(error, is_json=False):
        """
        Handle database-related errors
        
        Args:
            error: Database exception
            is_json: Whether to return JSON response
        """
        # Rollback any pending transactions
        try:
            db.session.rollback()
        except:
            pass
        
        # Determine error type and message
        if isinstance(error, IntegrityError):
            error_message = "Data integrity violation. Please check your input and try again."
            error_details = "Database constraint violation"
        elif isinstance(error, OperationalError):
            error_message = "Database operation failed. Please try again later."
            error_details = "Database connection or operation error"
        else:
            error_message = "A database error occurred. Please try again later."
            error_details = "General database error"
        
        # Log the error
        ErrorLogger.log_error(error, **{'error_type': 'database'})
        
        if is_json:
            return ErrorRenderer.render_json_error(500, error_message, error_details)
        else:
            flash(error_message, 'danger')
            return ErrorRenderer.render_error_page(500, error_message, error_details)
    
    @staticmethod
    def handle_security_error(error_type, details, is_json=False):
        """
        Handle security-related errors
        
        Args:
            error_type: Type of security error
            details: Error details
            is_json: Whether to return JSON response
        """
        # Enhanced logging with ValidationAuditor
        ValidationAuditor.log_security_violation(error_type, details)
        
        # Legacy logging for compatibility
        ErrorLogger.log_security_event(error_type, details)
        
        error_messages = {
            'csrf_token': "Security token expired or invalid. Please refresh the page and try again.",
            'sql_injection': "Invalid input detected. Please contact support if this persists.",
            'xss': "Invalid input detected. Please contact support if this persists.",
            'unauthorized_access': "You don't have permission to access this resource.",
            'rate_limit': "Too many requests. Please try again later."
        }
        
        error_message = error_messages.get(error_type, "Security validation failed.")
        
        if is_json:
            return ErrorRenderer.render_json_error(403, error_message, {'security_error': error_type})
        else:
            flash(error_message, 'danger')
            return ErrorRenderer.render_error_page(403, error_message, {'security_error': error_type})
    
    @staticmethod
    def handle_business_logic_error(error, is_json=False):
        """
        Handle business logic validation errors
        
        Args:
            error: Business logic exception
            is_json: Whether to return JSON response
        """
        # Log business logic error
        ErrorLogger.log_error(error, **{'error_type': 'business_logic'})
        
        error_message = str(error)
        
        if is_json:
            return ErrorRenderer.render_json_error(400, error_message, {'business_logic_error': True})
        else:
            flash(error_message, 'warning')
            return redirect(request.referrer or url_for('index'))


# Flask error handlers
def register_error_handlers(app):
    """Register all error handlers with Flask app"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors"""
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                400, 
                "Bad request", 
                getattr(error, 'description', 'Invalid request parameters')
            )
        return ErrorRenderer.render_error_page(400, "Bad request")
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors"""
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                401, 
                "Unauthorized", 
                "Authentication required"
            )
        flash('Please log in to access this page.', 'info')
        return redirect(url_for('auth.login', next=request.url))
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors"""
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                403, 
                "Forbidden", 
                "You don't have permission to access this resource"
            )
        return ErrorRenderer.render_error_page(403)
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors"""
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                404, 
                "Not found", 
                "The requested resource was not found"
            )
        return ErrorRenderer.render_error_page(404)
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        """Handle 429 Too Many Requests errors"""
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                429, 
                "Rate limit exceeded", 
                "Too many requests. Please try again later."
            )
        return ErrorRenderer.render_error_page(429, "Too many requests")
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error"""
        return ErrorHandler.handle_database_error(error, request.path.startswith('/api/'))
    
    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(error):
        """Handle SQLAlchemy errors"""
        return ErrorHandler.handle_database_error(error, request.path.startswith('/api/'))
    
    @app.errorhandler(ValidationError)
    def handle_validation_error_func(error):
        """Handle custom validation errors"""
        return ErrorHandler.handle_validation_error(error, request.path.startswith('/api/'))
    
    @app.errorhandler(Exception)
    def handle_general_exception(error):
        """Handle all other exceptions"""
        # Log the error
        ErrorLogger.log_error(error)
        
        # Check if it's a security-related error
        error_str = str(error).lower()
        if 'csrf' in error_str or 'token' in error_str:
            return ErrorHandler.handle_security_error('csrf_token', error_str, request.path.startswith('/api/'))
        
        if request.path.startswith('/api/'):
            return ErrorRenderer.render_json_error(
                500, 
                "Internal server error", 
                "An unexpected error occurred"
            )
        
        return ErrorRenderer.render_error_page(500, "An unexpected error occurred")


# Decorator for route-level error handling
def handle_errors(allow_json=True, log_errors=True):
    """
    Decorator for handling errors in routes
    
    Args:
        allow_json: Whether to allow JSON responses for API requests
        log_errors: Whether to log errors
    """
    def decorator(f):
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except ValidationError as e:
                return ErrorHandler.handle_validation_error(e, allow_json and request.path.startswith('/api/'))
            except SQLAlchemyError as e:
                return ErrorHandler.handle_database_error(e, allow_json and request.path.startswith('/api/'))
            except Exception as e:
                if log_errors:
                    ErrorLogger.log_error(e)
                
                if allow_json and request.path.startswith('/api/'):
                    return ErrorRenderer.render_json_error(500, "Internal server error")
                else:
                    flash("An unexpected error occurred. Please try again.", "danger")
                    return redirect(request.referrer or url_for('index'))
        
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator