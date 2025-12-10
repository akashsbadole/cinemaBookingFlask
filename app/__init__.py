"""
Cinema POS Application Package
"""
import os
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_required
from flask_wtf.csrf import CSRFProtect
from config import config
from app.database import db

# Initialize extensions
login_manager = LoginManager()
csrf = CSRFProtect()

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
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
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
    
    # Import models to ensure they are registered with SQLAlchemy
    from app import models
    from app.auth import models as auth_models
    from app.movies import models as movies_models
    from app.screens import models as screens_models
    from app.bookings import models as bookings_models
    from app.payments import models as payments_models
    
    # Main route
    @app.route('/')
    def index():
        """Main dashboard page"""
        if current_user.is_authenticated:
            return render_template('dashboard.html')
        return redirect(url_for('auth.login'))
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    # Context processor to make variables available in all templates
    @app.context_processor
    def inject_conf_vars():
        return dict(
            app_name='Cinema POS System',
            version='1.0.0'
        )
    
    return app

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from app.auth.models import User
    return User.query.get(int(user_id))