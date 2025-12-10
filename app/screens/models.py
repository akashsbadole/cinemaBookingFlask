"""
Screens Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Screen(db.Model):
    """Screen model"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    total_rows = db.Column(db.Integer, nullable=False)
    total_columns = db.Column(db.Integer, nullable=False)
    
    # Relationships
    seats = db.relationship('Seat', backref='screen', lazy=True)
    shows = db.relationship('Show', backref='screen', lazy=True)
    
    def __repr__(self):
        return f'<Screen {self.name}>'

class Seat(db.Model):
    """Seat model"""
    id = db.Column(db.Integer, primary_key=True)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), nullable=False)
    row = db.Column(db.String(2), nullable=False)
    column = db.Column(db.Integer, nullable=False)
    type = db.Column(db.Enum('normal', 'premium', 'vip', name='seat_types'), default='normal', nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    booking_seats = db.relationship('BookingSeat', backref='seat', lazy=True)
    
    # Unique constraint for seat within a screen
    __table_args__ = (db.UniqueConstraint('screen_id', 'row', 'column', name='_seat_location_uc'),)
    
    def __repr__(self):
        return f'<Seat {self.row}{self.column}>'