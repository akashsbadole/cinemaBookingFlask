"""
Shared Models
"""
# Import db from database module to avoid circular imports
# Import models from other modules to provide centralized access
from app.database import db
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.auth.models import User
from app.shows.models import Show