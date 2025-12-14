"""
Authentication Models
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import re

# Import db from database module to avoid circular imports
from app.database import db

class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False,
                       comment="Unique username for login")
    email = db.Column(db.String(120), index=True, unique=True, nullable=False,
                      comment="Unique email address")
    password_hash = db.Column(db.String(128), nullable=False,
                            comment="Hashed password")
    role = db.Column(db.Enum('admin', 'cashier', name='user_roles'), default='cashier', nullable=False,
                    comment="User role for permissions")
    last_login = db.Column(db.DateTime, default=None,
                         comment="Timestamp of last login")
    is_active = db.Column(db.Boolean, default=True, nullable=False,
                        comment="Whether user account is active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                          comment="Account creation timestamp")
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), default=None,
                         comment="ID of user who created this account")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                          comment="Last update timestamp")
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), default=None,
                         comment="ID of user who last updated this account")
    
    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy=True)
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint('length(username) >= 3', name='check_username_length'),
        db.CheckConstraint('length(email) >= 5', name='check_email_length'),
        db.CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name='check_email_format'),
        db.CheckConstraint("username ~* '^[a-zA-Z0-9_]+$'", name='check_username_format'),
        db.CheckConstraint("role IN ('admin', 'cashier')", name='check_role_values'),
        db.Index('idx_user_email_active', 'email', 'is_active'),
        db.Index('idx_user_username_active', 'username', 'is_active'),
    )
    
    def set_password(self, password):
        """Set password hash"""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Check password strength
        if not re.search(r'[A-Z]', password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            raise ValueError("Password must contain at least one digit")
        
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'
    
    def is_cashier(self):
        """Check if user is cashier"""
        return self.role == 'cashier'
    
    def validate_email(self, email):
        """Validate email format"""
        pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_username(self, username):
        """Validate username format"""
        pattern = r'^[a-zA-Z0-9_]{3,64}$'
        return re.match(pattern, username) is not None
    
    @staticmethod
    def validate_unique_email(email, exclude_id=None):
        """Check if email is unique"""
        query = User.query.filter_by(email=email)
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        return query.first() is None
    
    @staticmethod
    def validate_unique_username(username, exclude_id=None):
        """Check if username is unique"""
        query = User.query.filter_by(username=username)
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        return query.first() is None
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def to_dict(self):
        """Convert user to dictionary for API responses"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def from_dict(data, new_user=False):
        """Create user from dictionary"""
        user = User()
        
        if 'username' in data:
            if not user.validate_username(data['username']):
                raise ValueError("Invalid username format")
            user.username = data['username']
        
        if 'email' in data:
            if not user.validate_email(data['email']):
                raise ValueError("Invalid email format")
            user.email = data['email']
        
        if 'role' in data and data['role'] in ['admin', 'cashier']:
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])
        
        if new_user and 'password' in data:
            user.set_password(data['password'])
        
        return user