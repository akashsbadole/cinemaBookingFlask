"""
Booking utilities for seat management and availability checking
"""
from datetime import datetime, timedelta
import io
import qrcode
from flask import send_file
from app.database import db
from app.bookings.models import Booking, BookingSeat
from app.screens.models import Seat


class SeatManager:
    """Utility class for managing seat operations"""
    
    @staticmethod
    def get_available_seats(show_id):
        """Get list of available seats for a show"""
        from app.shows.models import Show
        
        show = Show.query.get(show_id)
        if not show:
            return []
        
        # Get all seats for the screen
        all_seats = show.screen.seats
        
        # Get booked/locked seats for this show
        booked_seat_ids = db.session.query(BookingSeat.seat_id).join(Booking).filter(
            Booking.show_id == show_id,
            Booking.status.in_(['pending', 'confirmed'])
        ).all()
        booked_seat_ids = [seat_id[0] for seat_id in booked_seat_ids]
        
        # Filter available seats
        available_seats = [seat for seat in all_seats if seat.id not in booked_seat_ids]
        return sorted(available_seats, key=lambda x: (x.row, x.column))
    
    @staticmethod
    def get_seat_layout(show_id):
        """Get seat layout with availability status for a show"""
        from app.shows.models import Show
        
        show = Show.query.get(show_id)
        if not show:
            return {}
        
        # Get all seats and organize by row
        seat_layout = {}
        for seat in show.screen.seats:
            if seat.row not in seat_layout:
                seat_layout[seat.row] = []
            seat_layout[seat.row].append(seat)
        
        # Get booked/locked seats
        booked_seats = db.session.query(BookingSeat.seat_id, BookingSeat.status).join(Booking).filter(
            Booking.show_id == show_id,
            Booking.status.in_(['pending', 'confirmed'])
        ).all()
        
        booked_seat_map = {seat_id: status for seat_id, status in booked_seats}
        
        # Add status to each seat
        layout_with_status = {}
        for row, seats in seat_layout.items():
            layout_with_status[row] = []
            for seat in sorted(seats, key=lambda x: x.column):
                seat_info = {
                    'id': seat.id,
                    'row': seat.row,
                    'column': seat.column,
                    'seat_type': seat.seat_type,
                    'status': 'available'
                }
                
                if seat.id in booked_seat_map:
                    seat_info['status'] = booked_seat_map[seat.id]
                
                layout_with_status[row].append(seat_info)
        
        return layout_with_status
    
    @staticmethod
    def lock_seats(show_id, seat_ids, duration_minutes=5, user_id=None):
        """Lock multiple seats for a specified duration (default 5 minutes)"""
        try:
            # Ensure seat_ids is a list
            if isinstance(seat_ids, int):
                seat_ids = [seat_ids]
            elif not isinstance(seat_ids, list):
                raise Exception("Invalid seat IDs format")
            
            # Clean up expired locks first
            SeatManager.cleanup_expired_locks()
            
            # Check if seats are available
            locked_seats = []
            for seat_id in seat_ids:
                # Check if seat is already booked/locked
                existing_booking = db.session.query(BookingSeat).join(Booking).filter(
                    BookingSeat.seat_id == seat_id,
                    Booking.show_id == show_id,
                    Booking.status.in_(['pending', 'confirmed'])
                ).first()
                
                if existing_booking:
                    # Release any expired locks first
                    if existing_booking.is_lock_expired():
                        db.session.delete(existing_booking)
                    else:
                        seat = Seat.query.get(seat_id)
                        seat_name = f"{seat.row}{seat.column}" if seat else f"Seat {seat_id}"
                        raise Exception(f"Seat {seat_name} is already {existing_booking.status}")
                
                # Create temporary booking seat entry for lock
                booking_seat = BookingSeat(
                    seat_id=seat_id,
                    status='locked',
                    price=0  # Will be calculated later
                )
                booking_seat.lock_seat(duration_minutes)
                locked_seats.append(booking_seat)
                db.session.add(booking_seat)
            
            db.session.commit()
            return locked_seats
        
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def release_seat_locks(show_id, seat_ids):
        """Release locks for specified seats"""
        try:
            # Ensure seat_ids is a list
            if isinstance(seat_ids, int):
                seat_ids = [seat_ids]
            elif not isinstance(seat_ids, list):
                raise Exception("Invalid seat IDs format")
                
            released_count = 0
            for seat_id in seat_ids:
                # Find locked seats for this show and seat
                locked_seats = db.session.query(BookingSeat).join(Booking).filter(
                    BookingSeat.seat_id == seat_id,
                    Booking.show_id == show_id,
                    BookingSeat.status == 'locked',
                    Booking.status == 'pending'  # Only release from pending bookings
                ).all()
                
                for locked_seat in locked_seats:
                    # Only release if not associated with a confirmed booking
                    if not locked_seat.booking or locked_seat.booking.status == 'pending':
                        db.session.delete(locked_seat)
                        released_count += 1
            
            db.session.commit()
            return released_count
        
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def cleanup_expired_locks():
        """Clean up all expired seat locks system-wide"""
        try:
            # Find all expired locked seats
            expired_seats = db.session.query(BookingSeat).filter(
                BookingSeat.status == 'locked',
                BookingSeat.lock_expiry < datetime.utcnow()
            ).all()
            
            # Delete expired locks
            for seat in expired_seats:
                db.session.delete(seat)
            
            if expired_seats:
                db.session.commit()
            
            return len(expired_seats)
        except Exception as e:
            db.session.rollback()
            raise e
    
    @staticmethod
    def validate_seat_availability(show_id, seat_ids):
        """Validate if specified seats are available for booking"""
        from app.shows.models import Show
        
        # Ensure seat_ids is a list
        if isinstance(seat_ids, int):
            seat_ids = [seat_ids]
        elif not isinstance(seat_ids, list):
            return False, "Invalid seat IDs format"
        
        show = Show.query.get(show_id)
        if not show:
            return False, "Show not found"
        
        # Clean up expired locks first
        SeatManager.cleanup_expired_locks()
        
        # Check if seats exist in the screen
        screen_seat_ids = [seat.id for seat in show.screen.seats]
        invalid_seats = [sid for sid in seat_ids if sid not in screen_seat_ids]
        if invalid_seats:
            return False, f"Invalid seats: {invalid_seats}"
        
        # Check seat availability
        for seat_id in seat_ids:
            existing_booking = db.session.query(BookingSeat).join(Booking).filter(
                BookingSeat.seat_id == seat_id,
                Booking.show_id == show_id,
                Booking.status.in_(['pending', 'confirmed'])
            ).first()
            
            if existing_booking:
                seat = Seat.query.get(seat_id)
                seat_name = f"{seat.row}{seat.column}" if seat else f"Seat {seat_id}"
                return False, f"Seat {seat_name} is already {existing_booking.status}"
        
        return True, "All seats are available"


class BookingCalculator:
    """Utility class for calculating booking costs"""
    
    @staticmethod
    def calculate_booking_cost(show_id, seat_ids):
        """Calculate total cost for booking specified seats in a show"""
        from app.shows.models import Show
        from app.screens.models import Seat
        
        # Ensure seat_ids is a list
        if isinstance(seat_ids, int):
            seat_ids = [seat_ids]
        elif not isinstance(seat_ids, list):
            return 0, "Invalid seat IDs format"
        
        show = Show.query.get(show_id)
        if not show:
            return 0, "Show not found"
        
        total_cost = 0
        seat_costs = []
        
        for seat_id in seat_ids:
            seat = Seat.query.get(seat_id)
            if not seat:
                return 0, f"Seat {seat_id} not found"
            
            # Calculate price based on show pricing and seat type
            seat_price = show.calculate_price(seat.seat_type)
            total_cost += seat_price
            
            seat_costs.append({
                'seat_id': seat_id,
                'seat_name': f"{seat.row}{seat.column}",
                'seat_type': seat.seat_type,
                'price': seat_price
            })
        
        return total_cost, seat_costs
    
    @staticmethod
    def get_price_breakdown(show_id, seat_ids):
        """Get detailed price breakdown for booking"""
        from app.shows.models import Show
        from app.screens.models import Seat
        
        # Ensure seat_ids is a list
        if isinstance(seat_ids, int):
            seat_ids = [seat_ids]
        elif not isinstance(seat_ids, list):
            return {'error': 'Invalid seat IDs format'}
        
        show = Show.query.get(show_id)
        if not show:
            return {}
        
        breakdown = {
            'show_info': {
                'id': show.id,
                'movie_title': show.movie.title,
                'screen_name': show.screen.name,
                'show_date': show.show_date.strftime('%d %b %Y'),
                'show_time': show.show_time.strftime('%I:%M %p'),
                'base_price': float(show.base_price),
                'is_weekend': show.is_weekend(),
                'is_matinee': show.is_matinee()
            },
            'seats': [],
            'total_amount': 0,
            'seat_count': len(seat_ids)
        }
        
        total = 0
        for seat_id in seat_ids:
            seat = Seat.query.get(seat_id)
            if seat:
                seat_price = show.calculate_price(seat.seat_type)
                
                seat_info = {
                    'id': seat.id,
                    'name': f"{seat.row}{seat.column}",
                    'type': seat.seat_type,
                    'base_price': float(show.base_price),
                    'weekend_surcharge': float(show.weekend_surcharge or 0) if show.is_weekend() else 0,
                    'matinee_discount': float(show.matinee_discount or 0) if show.is_matinee() else 0,
                    'type_multiplier': 1.5 if seat.seat_type == 'premium' else (2.0 if seat.seat_type == 'vip' else 1.0),
                    'final_price': seat_price
                }
                
                breakdown['seats'].append(seat_info)
                total += seat_price
        
        breakdown['total_amount'] = total
        return breakdown

def generate_qr_code(data):
    """Generate QR code for the given data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return img_io

def get_available_seats(show_id):
    """Get available seats for a show"""
    return SeatManager.get_available_seats(show_id)

def validate_booking_rules(show_id, seat_ids, user_id=None):
    """Validate booking rules and constraints"""
    from app.shows.models import Show
    
    # Ensure seat_ids is a list
    if isinstance(seat_ids, int):
        seat_ids = [seat_ids]
    elif not isinstance(seat_ids, list):
        return False, "Invalid seat IDs format"
    
    show = Show.query.get(show_id)
    if not show:
        return False, "Show not found"
    
    # Check maximum seats per booking
    if len(seat_ids) > 10:
        return False, "Maximum 10 seats allowed per booking"
    
    # Check if show is in the future
    if show.show_date < datetime.now().date():
        return False, "Cannot book past shows"
    
    # Check if show is already started
    show_datetime = datetime.combine(show.show_date, show.show_time)
    if show_datetime <= datetime.now():
        return False, "Show has already started"
    
    # Check seat availability
    return SeatManager.validate_seat_availability(show_id, seat_ids)