"""
Bookings Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Booking(db.Model):
    """Booking model"""
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum('cash', 'card', 'upi', name='payment_methods'), nullable=False)
    customer_name = db.Column(db.String(100))
    
    # Relationships
    booking_seats = db.relationship('BookingSeat', backref='booking', lazy=True)
    payments = db.relationship('Payment', backref='booking', lazy=True)
    
    def __repr__(self):
        return f'<Booking {self.id}>'

class BookingSeat(db.Model):
    """BookingSeat model for seat reservations"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    status = db.Column(db.Enum('booked', 'locked', name='booking_seat_status'), default='booked', nullable=False)
    
    def __repr__(self):
        return f'<BookingSeat {self.booking_id}-{self.seat_id}>'