"""
Bookings Models
"""
from datetime import datetime
import re

# Import db from database module to avoid circular imports
from app.database import db

class Booking(db.Model):
    """Booking model"""
    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True, nullable=False,
                              comment="Unique booking reference number")
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'), nullable=False,
                        comment="ID of the show")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False,
                        comment="ID of the user who made the booking")
    booking_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                            comment="Timestamp when booking was made")
    total_amount = db.Column(db.Numeric(10, 2), nullable=False,
                            comment="Total amount for the booking")
    payment_method = db.Column(db.Enum('cash', 'card', 'upi', 'paypal', 'netbanking', 'wallet', name='payment_methods'),
                             nullable=False, comment="Payment method used")
    customer_name = db.Column(db.String(100), nullable=False,
                            comment="Name of the customer")
    customer_phone = db.Column(db.String(20),
                             comment="Customer phone number")
    customer_email = db.Column(db.String(120),
                             comment="Customer email address")
    payment_reference = db.Column(db.String(100),
                                comment="Payment reference number")
    status = db.Column(db.Enum('pending', 'confirmed', 'cancelled', name='booking_status'),
                      default='pending', nullable=False, comment="Current booking status")
    notes = db.Column(db.Text, comment="Additional notes")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False,
                          comment="Creation timestamp")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                          comment="Last update timestamp")
    
    # Relationships
    booking_seats = db.relationship('BookingSeat', backref='booking', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='booking', lazy=True)
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint('total_amount >= 0', name='check_booking_amount_positive'),
        db.CheckConstraint('length(reference_number) >= 5', name='check_reference_length'),
        db.CheckConstraint('length(customer_name) >= 2', name='check_customer_name_length'),
        db.CheckConstraint("status IN ('pending', 'confirmed', 'cancelled')", name='check_booking_status'),
        db.CheckConstraint("payment_method IN ('cash', 'card', 'upi', 'paypal', 'netbanking', 'wallet')", name='check_payment_method'),
        db.CheckConstraint("customer_phone ~* '^[0-9+\-\s()]*$' OR customer_phone IS NULL", name='check_phone_format'),
        db.CheckConstraint("customer_email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$' OR customer_email IS NULL", name='check_email_format'),
        db.Index('idx_booking_reference', 'reference_number'),
        db.Index('idx_booking_status', 'status'),
        db.Index('idx_booking_show', 'show_id'),
        db.Index('idx_booking_user', 'user_id'),
        db.Index('idx_booking_time', 'booking_time'),
        db.UniqueConstraint('show_id', 'customer_email', 'customer_phone', name='uq_booking_customer_show'),
    )
    
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