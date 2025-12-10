"""
Payments Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Payment(db.Model):
    """Payment model"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    mode = db.Column(db.Enum('cash', 'card', 'upi', name='payment_modes'), nullable=False)
    reference_id = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<Payment {self.id}>'