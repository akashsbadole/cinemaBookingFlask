"""
Bookings Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Booking(db.Model):
    """Booking model"""
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.Enum('cash', 'card', 'upi', name='payment_methods'), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20))
    customer_email = db.Column(db.String(120))
    payment_reference = db.Column(db.String(100))
    status = db.Column(db.Enum('pending', 'confirmed', 'cancelled', name='booking_status'), default='pending')
    
    # Relationships
    booking_seats = db.relationship('BookingSeat', backref='booking', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='booking', lazy=True)
    
    def __repr__(self):
        return f'<Booking {self.reference_number}>'
    
    def generate_reference_number(self):
        """Generate a unique booking reference number"""
        import random
        import string
        
        if not self.reference_number:
            # Generate format: BK + year + month + random 6 digits
            now = datetime.utcnow()
            year_month = now.strftime('%y%m')
            random_chars = ''.join(random.choices(string.digits, k=6))
            self.reference_number = f'BK{year_month}{random_chars}'
            
            # Ensure uniqueness
            while Booking.query.filter_by(reference_number=self.reference_number).first():
                random_chars = ''.join(random.choices(string.digits, k=6))
                self.reference_number = f'BK{year_month}{random_chars}'
    
    def confirm_booking(self):
        """Confirm the booking"""
        self.status = 'confirmed'
        # Update all seat statuses to 'booked'
        for booking_seat in self.booking_seats:
            booking_seat.status = 'booked'
    
    def cancel_booking(self):
        """Cancel the booking and release seats"""
        self.status = 'cancelled'
        # Delete booking seats to release them
        for booking_seat in self.booking_seats:
            db.session.delete(booking_seat)
    
    def get_seat_count(self):
        """Get total number of seats in this booking"""
        return len(self.booking_seats)
    
    def get_seats_list(self):
        """Get list of seat identifiers"""
        seats = []
        for booking_seat in self.booking_seats:
            if booking_seat.seat:
                seats.append(f"{booking_seat.seat.row}{booking_seat.seat.column}")
        return seats

class BookingSeat(db.Model):
    """BookingSeat model for seat reservations and locking"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    status = db.Column(db.Enum('booked', 'locked', name='booking_seat_status'), default='booked', nullable=False)
    lock_time = db.Column(db.DateTime)
    lock_expiry = db.Column(db.DateTime)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    seat = db.relationship('Seat', backref='seat_bookings', overlaps="screen_seat")
    
    def __repr__(self):
        return f'<BookingSeat {self.booking_id}-{self.seat_id}>'
    
    def lock_seat(self, duration_minutes=10):
        """Lock a seat for the specified duration"""
        from datetime import timedelta
        
        self.status = 'locked'
        self.lock_time = datetime.utcnow()
        self.lock_expiry = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    def is_lock_expired(self):
        """Check if seat lock has expired"""
        if self.status == 'locked' and self.lock_expiry:
            return datetime.utcnow() > self.lock_expiry
        return False
    
    def release_lock(self):
        """Release the seat lock"""
        self.status = 'booked'
        self.lock_time = None
        self.lock_expiry = None
    
    @staticmethod
    def cleanup_expired_locks():
        """Clean up all expired seat locks"""
        expired_seats = BookingSeat.query.filter(
            BookingSeat.status == 'locked',
            BookingSeat.lock_expiry < datetime.utcnow()
        ).all()
        
        for seat in expired_seats:
            if seat.booking_id:  # If associated with a booking
                db.session.delete(seat)
            else:  # Just release the lock
                seat.release_lock()
        
        db.session.commit()
        return len(expired_seats)