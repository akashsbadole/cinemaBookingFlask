"""
Authentication Forms
"""
import re
from flask_wtf import FlaskForm
from flask_login import current_user
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.auth.models import User
from app.validators import DataValidators, InputSanitizer, SecurityValidator
from app.enhanced_validators import (
    DatabaseConstraintValidators,
    ValidationAuditor,
    validate_unique_field,
    validate_async_field
)

class LoginForm(FlaskForm):
    """Login form"""
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=1, max=64, message='Username must be between 1 and 64 characters')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
    
    def validate_username(self, field):
        """Validate and sanitize username"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=64)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            field.data = sanitized
    
    def validate_password(self, field):
        """Validate password without logging it"""
        if field.data:
            # Check for suspicious patterns
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in password')

class RegistrationForm(FlaskForm):
    """Registration form"""
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=64, message='Username must be between 3 and 64 characters'),
        validate_unique_field(User, 'username'),
        validate_async_field('username')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Length(min=5, max=64, message='Email must be between 5 and 64 characters'),
        Email(message='Please enter a valid email address'),
        validate_unique_field(User, 'email'),
        validate_async_field('email')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, max=128, message='Password must be between 8 and 128 characters')
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    role = SelectField('Role', choices=[('cashier', 'Cashier'), ('admin', 'Admin')], default='cashier')
    is_shared_account = BooleanField('Shared Account (Admin & Cashier can use same login)', default=False)
    submit = SubmitField('Register')
    
    def validate_username(self, field):
        """Validate and sanitize username"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=64)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Validate username uniqueness
            user = User.query.filter_by(username=sanitized).first()
            if user is not None:
                raise ValidationError('Please use a different username.')
    
    def validate_email(self, field):
        """Validate and sanitize email"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid email address')
            
            # Check for suspicious patterns
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in email')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Validate email uniqueness
            user = User.query.filter_by(email=sanitized).first()
            if user is not None:
                raise ValidationError('Please use a different email address.')
    
    def validate_password(self, field):
        """Validate password strength"""
        if field.data:
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in password')
            
            # Use our centralized password validator
            is_valid, error_message = DataValidators.validate_password_strength(field.data)
            if not is_valid:
                raise ValidationError(error_message)

class ProfileForm(FlaskForm):
    """Profile form for updating user information"""
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=64, message='Username must be between 3 and 64 characters'),
        validate_async_field('username')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Length(min=5, max=64, message='Email must be between 5 and 64 characters'),
        Email(message='Please enter a valid email address'),
        validate_async_field('email')
    ])
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required')
    ])
    new_password = PasswordField('New Password (optional)', validators=[
        Length(min=8, max=128, message='Password must be between 8 and 128 characters')
    ])
    new_password2 = PasswordField('Repeat New Password', validators=[
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Update Profile')
    
    def validate_username(self, field):
        """Validate and sanitize username"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=64)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in username')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Validate username uniqueness if changed
            if field.data != current_user.username:
                user = User.query.filter_by(username=sanitized).first()
                if user is not None:
                    raise ValidationError('Please use a different username.')
    
    def validate_email(self, field):
        """Validate and sanitize email"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid email address')
            
            # Check for suspicious patterns
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in email')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Validate email uniqueness if changed
            if field.data != current_user.email:
                user = User.query.filter_by(email=sanitized).first()
                if user is not None:
                    raise ValidationError('Please use a different email address.')
    
    def validate_current_password(self, field):
        """Validate current password"""
        if field.data:
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in password')
            
            # Verify current password
            if not current_user.check_password(field.data):
                raise ValidationError('Current password is incorrect.')
    
    def validate_new_password(self, field):
        """Validate new password strength if provided"""
        if field.data:
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in password')
            
            # Use our centralized password validator
            is_valid, error_message = DataValidators.validate_password_strength(field.data)
            if not is_valid:
                raise ValidationError(error_message)

class RoleSelectionForm(FlaskForm):
    """Form for selecting role for shared accounts"""
    selected_role = SelectField('Select Role', choices=[('admin', 'Administrator'), ('cashier', 'Cashier')], 
                               validators=[DataRequired(message='Please select a role')])
    submit = SubmitField('Continue')