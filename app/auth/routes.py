"""
Authentication Routes
"""
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.auth.models import User
from app.auth.forms import LoginForm, RegistrationForm, ProfileForm
from app.auth.decorators import admin_required
from app.database import db
from datetime import datetime, timedelta
import time

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route with rate limiting"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # Check rate limiting
    login_attempts = session.get('login_attempts', 0)
    last_attempt_time = session.get('last_attempt_time', 0)
    current_time = time.time()
    
    # Lock out for 5 minutes after 5 failed attempts
    if login_attempts >= 5 and current_time - last_attempt_time < 300:
        flash('Too many failed login attempts. Please try again in 5 minutes.', 'danger')
        return render_template('auth/login.html', title='Sign In', form=LoginForm())
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            # Increment failed attempts
            session['login_attempts'] = login_attempts + 1
            session['last_attempt_time'] = current_time
            
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Reset attempts on successful login
        session['login_attempts'] = 0
        session.pop('last_attempt_time', None)
        
        login_user(user, remember=form.remember_me.data)
        
        # Log the login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        next_page = request.args.get('next')
        if not next_page or url_for('index') not in next_page:
            next_page = url_for('index')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Sign In', form=form)

@bp.route('/logout')
@login_required
def logout():
    """Logout route"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
@login_required
@admin_required
def register():
    """Registration route (admin only)"""
    form = RegistrationForm()
    
    # Only show role field if current user is admin
    if current_user.is_admin():
        form.role.choices = [('cashier', 'Cashier'), ('admin', 'Admin')]
    else:
        form.role.choices = [('cashier', 'Cashier')]
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'User {form.username.data} has been created successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', title='Register User', form=form)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management route"""
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        
        # Update password if provided
        if form.new_password.data:
            current_user.set_password(form.new_password.data)
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    # Pre-fill form with current user data
    form.username.data = current_user.username
    form.email.data = current_user.email
    
    return render_template('auth/profile.html', title='Profile', form=form)