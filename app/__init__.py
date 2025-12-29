"""
Cinema POS Application Package
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, redirect, url_for, flash, session, abort
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from config import config
from app.database import db
from datetime import datetime

# Initialize extensions
login_manager = LoginManager()
csrf = CSRFProtect()
talisman = Talisman()

def create_app(config_name=None):
    """Application factory function"""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
    
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Initialize security headers with CSP - updated to allow external CDNs
    csp = {
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",  # Allow inline scripts for validation
            'https://www.paypal.com',
            'https://www.sandbox.paypal.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",  # Allow inline styles
            'https://fonts.googleapis.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'font-src': [
            "'self'",
            'https://fonts.gstatic.com',
            'https://cdnjs.cloudflare.com'
        ],
        'img-src': [
            "'self'",
            'data:',
            'https:',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ],
        'connect-src': [
            "'self'",
            'https://api.sandbox.paypal.com',
            'https://api.paypal.com',
            'https://cdn.jsdelivr.net',
            'https://cdnjs.cloudflare.com'
        ]
    }
    
    talisman.init_app(app, 
                     force_https=app.config.get('FORCE_HTTPS', False),
                     strict_transport_security=True,
                     content_security_policy=csp,
                     referrer_policy='strict-origin-when-cross-origin')
    
    # Configure logging
    configure_logging(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import and register error handlers
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.movies import bp as movies_bp
    app.register_blueprint(movies_bp, url_prefix='/movies')
    
    from app.screens import bp as screens_bp
    app.register_blueprint(screens_bp, url_prefix='/screens')
    
    from app.bookings import bp as bookings_bp
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    
    from app.payments import bp as payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    from app.shows import bp as shows_bp
    app.register_blueprint(shows_bp, url_prefix='/shows')
    
    from app.validation_api import validation_api
    app.register_blueprint(validation_api)
    
    # Register integration blueprint
    from app.integration import bp as integration_bp
    app.register_blueprint(integration_bp)
    
    # Import models to ensure they are registered with SQLAlchemy
    from app import models
    from app.auth import models as auth_models
    from app.movies import models as movies_models
    from app.screens import models as screens_models
    from app.bookings import models as bookings_models
    from app.payments import models as payments_models
    from app.shows import models as shows_models
    from app.integration.notifications import Notification, NotificationTemplate
    
    # Import validation and security components
    from app.validators import InputSanitizer, SecurityValidator
    from app.error_handlers import ErrorLogger
    from app.data_integrity import IntegrityChecker
    
    # Main route
    @app.route('/')
    def index():
        """Main dashboard page"""
        if current_user.is_authenticated:
            return render_template('dashboard.html')
        return redirect(url_for('auth.login'))
    
    # Context processor to make variables available in all templates
    @app.context_processor
    def inject_conf_vars():
        return dict(
            app_name='Cinema POS System',
            version='2.1.0'  # Updated version with comprehensive validation
        )
    
    # Enhanced security headers and validation
    @app.before_request
    def before_request():
        """Validate and sanitize request data before processing"""
        from flask import request, abort
        from datetime import timedelta
        
        # Skip for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return
        
        # Skip CSRF checks for safe HTTP methods
        if request.method in ['GET', 'HEAD', 'OPTIONS', 'TRACE']:
            return
        
        # Log suspicious activity for state-changing methods
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Check for common attack patterns
            suspicious_patterns = [
                '<script', 'javascript:', 'vbscript:', 'onload=', 'onerror=',
                'eval(', 'alert(', 'document.cookie', 'window.location',
                'union select', 'drop table', 'insert into', 'update set',
                'delete from', 'create table', 'alter table'
            ]
            
            # Check form data and JSON for suspicious patterns
            request_data = {}
            
            if request.is_json:
                request_data = request.get_json(silent=True) or {}
            elif request.form:
                request_data = request.form.to_dict()
            
            # Check for suspicious patterns in request data
            for key, value in request_data.items():
                if isinstance(value, str):
                    for pattern in suspicious_patterns:
                        if pattern.lower() in value.lower():
                            ErrorLogger.log_security_event(
                                'suspicious_request_pattern',
                                f'Suspicious pattern "{pattern}" detected in {key}',
                                request,
                                user_id=current_user.id if current_user.is_authenticated else None,
                                severity='high',
                                context={'key': key, 'pattern': pattern}
                            )
                            abort(400, "Suspicious input detected")
        
        # Validate session timeout only for authenticated users
        if current_user.is_authenticated:
            last_activity = session.get('last_activity')
            if last_activity:
                try:
                    last_activity_time = datetime.fromisoformat(last_activity)
                    if datetime.utcnow() - last_activity_time > timedelta(hours=24):
                        flash('Session expired due to inactivity', 'info')
                        from flask_login import logout_user
                        logout_user()
                        session.clear()  # Clear session data
                        return redirect(url_for('auth.login'))
                except ValueError:
                    # Invalid timestamp format, clear and continue
                    session.pop('last_activity', None)
            
            # Update last activity
            session['last_activity'] = datetime.utcnow().isoformat()
    
    @app.after_request
    def add_security_headers(response):
        """Add comprehensive security headers"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Remove server information
        response.headers['Server'] = ''
        
        return response
    
    # Health check endpoint for monitoring
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring"""
        try:
            # Check database connection
            db.session.execute('SELECT 1')
            
            # Run basic integrity checks
            integrity_status = IntegrityChecker.run_all_checks()
            
            return {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'integrity': integrity_status['summary']['overall_status']
            }, 200
        except Exception as e:
            return {
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }, 503
    
    return app

def configure_logging(app):
    """Configure comprehensive application logging"""
    if not app.debug:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Set up file handler for application logs
        file_handler = RotatingFileHandler(
            'logs/cinema_pos.log', 
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Set up error file handler
        error_handler = RotatingFileHandler(
            'logs/errors.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
        ))
        error_handler.setLevel(logging.ERROR)
        app.logger.addHandler(error_handler)
        
        # Set up security file handler
        security_handler = RotatingFileHandler(
            'logs/security.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        security_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s : %(message)s'
        ))
        security_handler.setLevel(logging.WARNING)
        security_logger = logging.getLogger('security')
        security_logger.addHandler(security_handler)
        
        # Set up audit file handler
        audit_handler = RotatingFileHandler(
            'logs/audit.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        audit_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s : %(message)s'
        ))
        audit_handler.setLevel(logging.INFO)
        audit_logger = logging.getLogger('audit')
        audit_logger.addHandler(audit_handler)

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from app.auth.models import User
    return User.query.get(int(user_id))
