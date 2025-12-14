"""
Authentication Routes
"""
from flask import render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.auth import bp
from app.auth.models import User
from app.auth.forms import LoginForm, RegistrationForm, ProfileForm
from app.auth.decorators import admin_required
from app.database import db
from app.validators import InputSanitizer, DataValidators, SecurityValidator, ValidationError
from app.error_handlers import ErrorLogger, ErrorHandler
from datetime import datetime, timedelta
import time
import logging

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route with rate limiting and enhanced validation"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Check rate limiting
    login_attempts = session.get('login_attempts', 0)
    last_attempt_time = session.get('last_attempt_time', 0)
    current_time = time.time()
    
    # Lock out for 5 minutes after 5 failed attempts
    if login_attempts >= 5 and current_time - last_attempt_time < 300:
        ErrorLogger.log_security_event(
            'login_rate_limit',
            f'Rate limit exceeded for login attempts. Attempts: {login_attempts}',
            request,
            session_data={'login_attempts': login_attempts}
        )
        flash('Too many failed login attempts. Please try again in 5 minutes.', 'danger')
        return render_template('auth/login.html', title='Sign In', form=LoginForm())
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            # Sanitize inputs
            username = InputSanitizer.sanitize_string(form.username.data, max_length=100)
            password = form.password.data  # Don't sanitize passwords
            
            # Security check for injection attempts
            if SecurityValidator.detect_sql_injection([username, password]):
                ErrorLogger.log_security_event(
                    'sql_injection_attempt',
                    f'SQL injection attempt detected in login: {username}',
                    request,
                    severity='high'
                )
                abort(400, "Invalid input detected")
            
            # Validate username format
            if not DataValidators.validate_username_format(username):
                flash('Invalid username format. Please use alphanumeric characters only.', 'danger')
                return render_template('auth/login.html', title='Sign In', form=form)
            
            # Check for suspicious patterns
            if SecurityValidator.is_suspicious_pattern(username):
                ErrorLogger.log_security_event(
                    'suspicious_login_pattern',
                    f'Suspicious pattern detected in username: {username}',
                    request,
                    severity='medium'
                )
            
            # Find user
            user = User.query.filter_by(username=username).first()
            
            # Validate password
            if user is None:
                # Increment failed attempts
                session['login_attempts'] = login_attempts + 1
                session['last_attempt_time'] = current_time
                
                ErrorLogger.log_security_event(
                    'login_failed_user_not_found',
                    f'Login attempt with non-existent username: {username}',
                    request,
                    session_data={'login_attempts': login_attempts + 1}
                )
                
                flash('Invalid username or password', 'danger')
                return render_template('auth/login.html', title='Sign In', form=form)
            
            if not user.check_password(password):
                # Increment failed attempts
                session['login_attempts'] = login_attempts + 1
                session['last_attempt_time'] = current_time
                
                ErrorLogger.log_security_event(
                    'login_failed_wrong_password',
                    f'Login attempt with wrong password for user: {username}',
                    request,
                    user_id=user.id,
                    session_data={'login_attempts': login_attempts + 1}
                )
                
                flash('Invalid username or password', 'danger')
                return render_template('auth/login.html', title='Sign In', form=form)
            
            # Check if user is active
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html', title='Sign In', form=form)
            
            # Reset attempts on successful login
            session['login_attempts'] = 0
            session.pop('last_attempt_time', None)
            
            login_user(user, remember=form.remember_me.data)
            
            # Log the login time
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            ErrorLogger.log_security_event(
                'login_success',
                f'User {username} logged in successfully',
                request,
                user_id=user.id
            )
            
            next_page = request.args.get('next')
            if not next_page or url_for('index') not in next_page:
                next_page = url_for('index')
            return redirect(next_page)
            
        except Exception as e:
            ErrorLogger.log_error(e, request_data={'username': form.username.data})
            ErrorHandler.handle_error(e, request)
            flash('An error occurred during login. Please try again.', 'danger')
            return render_template('auth/login.html', title='Sign In', form=form)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/logout')
@login_required
def logout():
    """Logout route with logging"""
    try:
        ErrorLogger.log_security_event(
            'logout',
            f'User {current_user.username} logged out',
            request,
            user_id=current_user.id
        )
        
        logout_user()
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('auth.login'))
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred during logout.', 'warning')
        return redirect(url_for('index'))

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register():
    """Registration route (admin only) with enhanced validation"""
    form = RegistrationForm()
    
    # Only show role field if current user is admin
    if current_user.is_admin():
        form.role.choices = [('cashier', 'Cashier'), ('admin', 'Admin')]
    else:
        form.role.choices = [('cashier', 'Cashier')]
    
    if form.validate_on_submit():
        try:
            # Sanitize inputs
            username = InputSanitizer.sanitize_string(form.username.data, max_length=100)
            email = InputSanitizer.sanitize_email(form.email.data)
            role = InputSanitizer.sanitize_string(form.role.data, max_length=20)
            password = form.password.data  # Don't sanitize passwords
            
            # Security checks
            if SecurityValidator.detect_sql_injection([username, email, role]):
                ErrorLogger.log_security_event(
                    'sql_injection_attempt',
                    f'SQL injection attempt detected in registration: {username}',
                    request,
                    user_id=current_user.id,
                    severity='high'
                )
                abort(400, "Invalid input detected")
            
            # Validate data formats
            if not DataValidators.validate_username_format(username):
                raise ValidationError("Invalid username format")
            
            if not DataValidators.validate_email_format(email):
                raise ValidationError("Invalid email format")
            
            if not DataValidators.validate_password_strength(password):
                raise ValidationError("Password does not meet security requirements")
            
            # Validate role
            if role not in ['admin', 'cashier']:
                raise ValidationError("Invalid role specified")
            
            # Check for existing username
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                raise ValidationError("Username already exists")
            
            # Check for existing email
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                raise ValidationError("Email already exists")
            
            # Create user
            user = User(
                username=username,
                email=email,
                role=role,
                created_at=datetime.utcnow(),
                created_by=current_user.id
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            ErrorLogger.log_security_event(
                'user_created',
                f'Admin {current_user.username} created new user: {username} with role: {role}',
                request,
                user_id=current_user.id,
                target_user_id=user.id
            )
            
            flash(f'User {username} has been created successfully!', 'success')
            return redirect(url_for('auth.login'))
            
        except ValidationError as e:
            ErrorLogger.log_security_event(
                'registration_validation_error',
                f'Validation error in registration: {str(e)}',
                request,
                user_id=current_user.id,
                severity='medium'
            )
            flash(str(e), 'danger')
            
        except Exception as e:
            db.session.rollback()
            ErrorLogger.log_error(e, request, user_id=current_user.id)
            ErrorHandler.handle_error(e, request)
            flash('An error occurred during user registration. Please try again.', 'danger')
    
    return render_template('auth/register.html', title='Register User', form=form)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management route with enhanced validation"""
    form = ProfileForm()
    
    if form.validate_on_submit():
        try:
            # Sanitize inputs
            username = InputSanitizer.sanitize_string(form.username.data, max_length=100)
            email = InputSanitizer.sanitize_email(form.email.data)
            new_password = form.new_password.data  # Don't sanitize passwords
            
            # Security checks
            if SecurityValidator.detect_sql_injection([username, email]):
                ErrorLogger.log_security_event(
                    'sql_injection_attempt',
                    f'SQL injection attempt detected in profile update: {username}',
                    request,
                    user_id=current_user.id,
                    severity='high'
                )
                abort(400, "Invalid input detected")
            
            # Validate data formats
            if not DataValidators.validate_username_format(username):
                raise ValidationError("Invalid username format")
            
            if not DataValidators.validate_email_format(email):
                raise ValidationError("Invalid email format")
            
            # Check for existing username (if changed)
            if username != current_user.username:
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    raise ValidationError("Username already exists")
            
            # Check for existing email (if changed)
            if email != current_user.email:
                existing_email = User.query.filter_by(email=email).first()
                if existing_email:
                    raise ValidationError("Email already exists")
            
            # Validate new password if provided
            if new_password and not DataValidators.validate_password_strength(new_password):
                raise ValidationError("Password does not meet security requirements")
            
            # Update user
            current_user.username = username
            current_user.email = email
            current_user.updated_at = datetime.utcnow()
            
            # Update password if provided
            if new_password:
                current_user.set_password(new_password)
                ErrorLogger.log_security_event(
                    'password_changed',
                    f'User {username} changed their password',
                    request,
                    user_id=current_user.id
                )
            
            db.session.commit()
            
            ErrorLogger.log_security_event(
                'profile_updated',
                f'User {username} updated their profile',
                request,
                user_id=current_user.id
            )
            
            flash('Your profile has been updated successfully!', 'success')
            return redirect(url_for('auth.profile'))
            
        except ValidationError as e:
            ErrorLogger.log_security_event(
                'profile_validation_error',
                f'Validation error in profile update: {str(e)}',
                request,
                user_id=current_user.id,
                severity='medium'
            )
            flash(str(e), 'danger')
            
        except Exception as e:
            db.session.rollback()
            ErrorLogger.log_error(e, request, user_id=current_user.id)
            ErrorHandler.handle_error(e, request)
            flash('An error occurred while updating your profile. Please try again.', 'danger')
    
    # Pre-fill form with current user data
    form.username.data = current_user.username
    form.email.data = current_user.email
    
    return render_template('auth/profile.html', title='Profile', form=form)
