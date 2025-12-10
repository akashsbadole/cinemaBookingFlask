"""
Authentication Forms
"""
import re
from flask_wtf import FlaskForm
from flask_login import current_user
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.auth.models import User

class LoginForm(FlaskForm):
    """Login form"""
    username = StringField('Username', validators=[DataRequired(), Length(1, 64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    """Registration form"""
    username = StringField('Username', validators=[DataRequired(), Length(1, 64)])
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(8, 128, message='Password must be between 8 and 128 characters'),
        # Custom password strength validator will be added below
    ])
    password2 = PasswordField('Repeat Password',
                             validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    role = SelectField('Role', choices=[('cashier', 'Cashier'), ('admin', 'Admin')], default='cashier')
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        """Validate username uniqueness"""
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')
    
    def validate_email(self, email):
        """Validate email uniqueness"""
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')
    
    def validate_password(self, password):
        """Validate password strength"""
        password_str = password.data
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password_str):
            raise ValidationError('Password must contain at least one uppercase letter.')
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password_str):
            raise ValidationError('Password must contain at least one lowercase letter.')
        
        # Check for at least one digit
        if not re.search(r'\d', password_str):
            raise ValidationError('Password must contain at least one digit.')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password_str):
            raise ValidationError('Password must contain at least one special character.')

class ProfileForm(FlaskForm):
    """Profile form for updating user information"""
    username = StringField('Username', validators=[DataRequired(), Length(1, 64)])
    email = StringField('Email', validators=[DataRequired(), Length(1, 64), Email()])
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password (optional)', validators=[
        Length(8, 128, message='Password must be between 8 and 128 characters')
    ])
    new_password2 = PasswordField('Repeat New Password',
                                 validators=[EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Update Profile')
    
    def validate_username(self, username):
        """Validate username uniqueness if changed"""
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')
    
    def validate_email(self, email):
        """Validate email uniqueness if changed"""
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError('Please use a different email address.')
    
    def validate_current_password(self, current_password):
        """Validate current password"""
        if not current_user.check_password(current_password.data):
            raise ValidationError('Current password is incorrect.')
    
    def validate_new_password(self, new_password):
        """Validate new password strength if provided"""
        if new_password.data:
            password_str = new_password.data
            
            # Check for at least one uppercase letter
            if not re.search(r'[A-Z]', password_str):
                raise ValidationError('New password must contain at least one uppercase letter.')
            
            # Check for at least one lowercase letter
            if not re.search(r'[a-z]', password_str):
                raise ValidationError('New password must contain at least one lowercase letter.')
            
            # Check for at least one digit
            if not re.search(r'\d', password_str):
                raise ValidationError('New password must contain at least one digit.')
            
            # Check for at least one special character
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password_str):
                raise ValidationError('New password must contain at least one special character.')