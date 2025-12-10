"""
Shared Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Show(db.Model):
    """Show model for movie screenings"""
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), nullable=False)
    show_date = db.Column(db.Date, nullable=False)
    show_time = db.Column(db.Time, nullable=False)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    bookings = db.relationship('Booking', backref='show', lazy=True)
    
    def __repr__(self):
        return f'<Show {self.id}>'