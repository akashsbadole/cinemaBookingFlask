"""
Shows Models
"""
from datetime import datetime, time

from app.database import db


class Show(db.Model):
    """Show model for movie screenings"""
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), nullable=False)
    show_date = db.Column(db.Date, nullable=False)
    show_time = db.Column(db.Time, nullable=False)
    
    # Pricing fields
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    weekend_surcharge = db.Column(db.Numeric(10, 2), default=0.00)  # Additional charge for weekends
    matinee_discount = db.Column(db.Numeric(10, 2), default=0.00)   # Discount for matinee shows
    
    # Scheduling fields
    end_time = db.Column(db.Time, nullable=False)  # Calculated from movie duration
    show_type = db.Column(db.Enum('regular', 'matinee', 'evening', 'night', name='show_types'), default='regular')
    
    # Status management
    status = db.Column(db.Enum('scheduled', 'cancelled', 'completed', name='show_status'), default='scheduled')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='show', lazy=True)
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('movie_id', 'screen_id', 'show_date', 'show_time', name='_show_schedule_uc'),
    )
    
    def __repr__(self):
        return f'<Show {self.id}: {self.movie.name} at {self.screen.name}>'
    
    def calculate_price(self, seat_type='normal'):
        """Calculate final price based on base price, show time, and seat type"""
        from app.screens.models import Seat
        
        # Start with base price
        price = float(self.base_price)
        
        # Add weekend surcharge if applicable
        if self.is_weekend():
            price += float(self.weekend_surcharge or 0)
        
        # Apply matinee discount if applicable
        if self.is_matinee():
            price -= float(self.matinee_discount or 0)
        
        # Add seat type multiplier
        if seat_type == 'premium':
            price *= 1.5
        elif seat_type == 'vip':
            price *= 2.0
        
        # Ensure minimum price
        price = max(price, 50.00)  # Minimum ₹50
        
        return round(price, 2)
    
    def is_weekend(self):
        """Check if show is on a weekend"""
        return self.show_date.weekday() >= 5  # 5=Saturday, 6=Sunday
    
    def is_matinee(self):
        """Check if show is a matinee show (before 12 PM)"""
        return self.show_time.hour < 12
    
    def get_available_seats(self):
        """Get list of available seats for this show"""
        from app.bookings.models import BookingSeat, Booking
        
        # Get all seats for the screen
        all_seats = self.screen.seats
        
        # Get booked seats for this show
        booked_seat_ids = db.session.query(BookingSeat.seat_id).join(Booking).filter(
            Booking.show_id == self.id
        ).all()
        booked_seat_ids = [seat_id[0] for seat_id in booked_seat_ids]
        
        # Filter available seats
        available_seats = [seat for seat in all_seats if seat.id not in booked_seat_ids]
        return available_seats
    
    def get_occupied_seats(self):
        """Get list of occupied seats for this show"""
        from app.bookings.models import BookingSeat, Booking
        from app.screens.models import Seat
        
        occupied_seats = db.session.query(Seat).join(BookingSeat).join(Booking).filter(
            Booking.show_id == self.id
        ).all()
        
        return occupied_seats
    
    def get_available_seats_count(self):
        """Get count of available seats for this show"""
        return len(self.get_available_seats())
    
    def get_total_seats_count(self):
        """Get total number of seats for this show's screen"""
        return len(self.screen.seats)
    
    def get_occupancy_percentage(self):
        """Get occupancy percentage for this show"""
        total_seats = self.get_total_seats_count()
        if total_seats == 0:
            return 0
        
        occupied_seats = total_seats - len(self.get_available_seats())
        return round((occupied_seats / total_seats) * 100, 2)
    
    def can_be_cancelled(self):
        """Check if show can be cancelled"""
        # Shows with bookings cannot be cancelled
        return len(self.bookings) == 0
    
    def get_duration_string(self):
        """Get formatted duration string"""
        if not hasattr(self.movie, 'duration'):
            return "Unknown"
        hours = self.movie.duration // 60
        minutes = self.movie.duration % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"