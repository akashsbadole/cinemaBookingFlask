"""
Seat Management Utilities
"""
from datetime import datetime, timedelta
from app.database import db
from app.screens.models import Screen, Seat, SeatLock
from decimal import Decimal


def check_seat_availability(seat_id, show_id):
    """
    Check if a seat is available for a specific show
    
    Args:
        seat_id (int): ID of the seat to check
        show_id (int): ID of the show to check
        
    Returns:
        dict: Availability information with status and details
    """
    # Import locally to avoid circular imports
    from app.bookings.models import BookingSeat
    from app.bookings.models import Booking
    
    # Check if seat exists
    seat = Seat.query.get(seat_id)
    if not seat:
        return {
            'available': False,
            'reason': 'Seat not found',
            'status': 'error'
        }
    
    # Check if seat is locked for this show
    if SeatLock.is_seat_locked(seat_id, show_id):
        return {
            'available': False,
            'reason': 'Seat is currently locked',
            'status': 'locked'
        }
    
    # Check if seat is booked for this show
    booking_seat = BookingSeat.query.filter_by(
        seat_id=seat_id
    ).join('booking').filter(
        BookingSeat.booking_id == Booking.id,
        Booking.show_id == show_id,
        Booking.status.in_(['confirmed', 'pending'])
    ).first()
    
    if booking_seat:
        return {
            'available': False,
            'reason': 'Seat already booked',
            'status': 'booked',
            'booking_status': booking_seat.status
        }
    
    return {
        'available': True,
        'seat': seat,
        'status': 'available'
    }


def get_seat_layout_with_availability(screen_id, show_id):
    """
    Get seat layout with availability status for a specific show
    
    Args:
        screen_id (int): ID of the screen
        show_id (int): ID of the show
        
    Returns:
        dict: Seat layout with availability information
    """
    # Import locally to avoid circular imports
    from app.bookings.models import BookingSeat
    from app.bookings.models import Booking
    
    screen = Screen.query.get(screen_id)
    if not screen:
        return None
    
    # Get all seats for the screen
    seats_grid = screen.get_seats_grid()
    
    # Get booked seats for this show
    booked_seats = db.session.query(BookingSeat.seat_id, BookingSeat.status).join(Booking).filter(
        Booking.show_id == show_id,
        Booking.status.in_(['confirmed', 'pending'])
    ).all()
    
    # Create a dictionary of seat_id -> status
    booked_status = {seat_id: status for seat_id, status in booked_seats}
    
    # Get locked seats for this show
    locked_seats = SeatLock.get_locked_seats_for_show(show_id)
    locked_seat_ids = {lock.seat_id for lock in locked_seats}
    
    # Build the layout with availability
    layout = {}
    seats_list = []
    
    for row_letter in seats_grid:
        layout[row_letter] = {}
        for col in seats_grid[row_letter]:
            seat = seats_grid[row_letter][col]
            
            # Determine seat status
            if seat.id in locked_seat_ids:
                seat_status = 'locked'
            elif seat.id in booked_status:
                seat_status = booked_status[seat.id]
            else:
                seat_status = 'available'
            
            seat_data = {
                'id': seat.id,
                'row': seat.row,
                'column': seat.column,
                'type': seat.type,
                'price': float(seat.price),
                'status': seat_status,
                'name': f"{seat.row}{seat.column}",
                'seat_number': seat.seat_number
            }
            
            layout[row_letter][col] = seat_data
            seats_list.append(seat_data)
    
    return {
        'screen': {
            'id': screen.id,
            'name': screen.name,
            'total_rows': screen.total_rows,
            'total_columns': screen.total_columns
        },
        'layout': layout,
        'seats': seats_list
    }


def lock_seats_for_booking(seat_ids, show_id, user_id, duration_minutes=10):
    """
    Lock multiple seats for a booking
    
    Args:
        seat_ids (list): List of seat IDs to lock
        show_id (int): ID of the show
        user_id (int): ID of the user making the booking
        duration_minutes (int): Duration of lock in minutes
        
    Returns:
        dict: Result with locked seats and any errors
    """
    locked_seats = []
    errors = []
    
    for seat_id in seat_ids:
        # Check availability first
        availability = check_seat_availability(seat_id, show_id)
        
        if not availability['available']:
            errors.append({
                'seat_id': seat_id,
                'reason': availability['reason'],
                'status': availability['status']
            })
            continue
        
        # Lock the seat using SeatLock model
        success, message = SeatLock.lock_seat(seat_id, show_id, user_id, duration_minutes)
        
        if success:
            locked_seats.append(availability['seat'])
        else:
            errors.append({
                'seat_id': seat_id,
                'reason': message,
                'status': 'lock_failed'
            })
    
    return {
        'locked_seats': locked_seats,
        'errors': errors,
        'success': len(locked_seats) > 0
    }


def release_seat_locks(seat_ids, show_id, user_id=None):
    """
    Release seat locks for the given seat IDs
    
    Args:
        seat_ids (list): List of seat IDs to release locks for
        show_id (int): ID of the show
        user_id (int, optional): ID of the user releasing the locks
        
    Returns:
        int: Number of locks released
    """
    released_count = 0
    
    for seat_id in seat_ids:
        if SeatLock.release_lock(seat_id, show_id, user_id):
            released_count += 1
    
    return released_count


def cleanup_expired_locks():
    """
    Clean up all expired seat locks in the system
    
    Returns:
        int: Number of locks cleaned up
    """
    return SeatLock.release_expired_locks()


def get_seat_utilization_report(screen_id, start_date=None, end_date=None):
    """
    Get seat utilization report for a screen within a date range
    
    Args:
        screen_id (int): ID of the screen
        start_date (datetime): Start date for the report (optional)
        end_date (datetime): End date for the report (optional)
        
    Returns:
        dict: Seat utilization statistics
    """
    from app.shows.models import Show
    
    screen = Screen.query.get(screen_id)
    if not screen:
        return None
    
    # Default to last 30 days if no dates provided
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()
    
    # Get shows for this screen in the date range
    shows = Show.query.filter(
        Show.screen_id == screen_id,
        Show.show_date >= start_date.date(),
        Show.show_date <= end_date.date(),
        Show.status.in_(['scheduled', 'completed'])
    ).all()
    
    total_seats = len(screen.seats)
    total_seat_capacity = total_seats * len(shows) if shows else 0
    total_booked_seats = 0
    
    # Calculate utilization by show type
    utilization_by_type = {
        'normal': {'total_capacity': 0, 'booked': 0},
        'premium': {'total_capacity': 0, 'booked': 0},
        'vip': {'total_capacity': 0, 'booked': 0}
    }
    
    for show in shows:
        # Get all seats for this screen
        for seat in screen.seats:
            utilization_by_type[seat.type]['total_capacity'] += 1
        
        # Get booked seats for this show
        from app.bookings.models import BookingSeat
        from app.bookings.models import Booking
        booked_seats = db.session.query(Seat).join(BookingSeat).join(Booking).filter(
            Booking.show_id == show.id,
            Booking.status == 'confirmed'
        ).all()
        
        total_booked_seats += len(booked_seats)
        
        # Count by seat type
        for seat in booked_seats:
            utilization_by_type[seat.type]['booked'] += 1
    
    # Calculate percentages
    overall_utilization = (total_booked_seats / total_seat_capacity * 100) if total_seat_capacity > 0 else 0
    
    for seat_type in utilization_by_type:
        capacity = utilization_by_type[seat_type]['total_capacity']
        booked = utilization_by_type[seat_type]['booked']
        utilization_by_type[seat_type]['utilization'] = (booked / capacity * 100) if capacity > 0 else 0
    
    return {
        'screen': {
            'id': screen.id,
            'name': screen.name,
            'total_seats': total_seats
        },
        'period': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_shows': len(shows)
        },
        'overall_utilization': round(overall_utilization, 2),
        'total_booked_seats': total_booked_seats,
        'total_seat_capacity': total_seat_capacity,
        'by_seat_type': utilization_by_type
    }


def update_seat_prices(screen_id, price_updates):
    """
    Update prices for multiple seats of different types
    
    Args:
        screen_id (int): ID of the screen
        price_updates (dict): Dictionary with seat types as keys and new prices as values
            Example: {'normal': 120.00, 'premium': 180.00, 'vip': 300.00}
        
    Returns:
        dict: Result with updated seats count
    """
    screen = Screen.query.get(screen_id)
    if not screen:
        return {'success': False, 'message': 'Screen not found'}
    
    updated_count = 0
    
    for seat_type, new_price in price_updates.items():
        if seat_type in ['normal', 'premium', 'vip']:
            seats = Seat.query.filter_by(
                screen_id=screen_id,
                type=seat_type
            ).all()
            
            for seat in seats:
                seat.price = Decimal(str(new_price))
                updated_count += 1
    
    db.session.commit()
    
    return {
        'success': True,
        'updated_count': updated_count,
        'message': f'Updated prices for {updated_count} seats'
    }


def bulk_update_seat_types(screen_id, type_updates):
    """
    Bulk update seat types for multiple seats
    
    Args:
        screen_id (int): ID of the screen
        type_updates (dict): Dictionary with seat identifiers as keys and new types as values
            Example: {'A1': 'premium', 'B5': 'vip', 'C3': 'normal'}
        
    Returns:
        dict: Result with updated seats and any errors
    """
    screen = Screen.query.get(screen_id)
    if not screen:
        return {'success': False, 'message': 'Screen not found'}
    
    updated_seats = []
    errors = []
    
    for seat_identifier, new_type in type_updates.items():
        if len(seat_identifier) < 2:
            errors.append({
                'seat': seat_identifier,
                'reason': 'Invalid seat identifier'
            })
            continue
        
        # Parse row and column
        row = seat_identifier[0].upper()
        try:
            column = int(seat_identifier[1:])
        except ValueError:
            errors.append({
                'seat': seat_identifier,
                'reason': 'Invalid seat number'
            })
            continue
        
        # Find the seat
        seat = Seat.query.filter_by(
            screen_id=screen_id,
            row=row,
            column=column
        ).first()
        
        if not seat:
            errors.append({
                'seat': seat_identifier,
                'reason': 'Seat not found'
            })
            continue
        
        # Check if seat has active bookings
        from app.bookings.models import BookingSeat
        from app.bookings.models import Booking
        active_bookings = BookingSeat.query.filter_by(seat_id=seat.id).join('booking').filter(
            Booking.status.in_(['confirmed', 'pending'])
        ).count()
        
        if active_bookings > 0:
            errors.append({
                'seat': seat_identifier,
                'reason': 'Seat has active bookings'
            })
            continue
        
        # Update seat type and adjust price if needed
        old_type = seat.type
        seat.type = new_type
        
        # Adjust price based on new type (using default prices)
        default_prices = {
            'normal': 100.00,
            'premium': 150.00,
            'vip': 250.00
        }
        
        # Keep the same price if it's already reasonable for the new type
        if new_type in default_prices:
            if old_type == 'normal' and new_type == 'premium':
                seat.price = max(seat.price * Decimal('1.5'), Decimal(str(default_prices[new_type])))
            elif old_type == 'normal' and new_type == 'vip':
                seat.price = max(seat.price * Decimal('2.0'), Decimal(str(default_prices[new_type])))
            elif old_type == 'premium' and new_type == 'vip':
                seat.price = max(seat.price * Decimal('1.33'), Decimal(str(default_prices[new_type])))
            elif old_type == 'premium' and new_type == 'normal':
                seat.price = min(seat.price / Decimal('1.5'), Decimal(str(default_prices[new_type])))
            elif old_type == 'vip' and new_type == 'premium':
                seat.price = min(seat.price / Decimal('1.33'), Decimal(str(default_prices[new_type])))
            elif old_type == 'vip' and new_type == 'normal':
                seat.price = min(seat.price / Decimal('2.0'), Decimal(str(default_prices[new_type])))
        
        updated_seats.append(seat)
    
    if updated_seats:
        db.session.commit()
    
    return {
        'success': len(updated_seats) > 0,
        'updated_seats': [f"{s.row}{s.column}" for s in updated_seats],
        'updated_count': len(updated_seats),
        'errors': errors
    }


def get_seat_pricing_matrix(screen_id):
    """
    Get pricing matrix for all seats in a screen
    
    Args:
        screen_id (int): ID of the screen
        
    Returns:
        dict: Pricing matrix with seat types and their prices
    """
    from app.screens.models import Screen
    
    screen = Screen.query.get(screen_id)
    if not screen:
        return None
    
    # Get all seats for the screen
    seats = Seat.query.filter_by(screen_id=screen_id).all()
    
    # Group by seat type and get price ranges
    pricing_matrix = {
        'normal': {'min': float('inf'), 'max': 0, 'count': 0, 'prices': []},
        'premium': {'min': float('inf'), 'max': 0, 'count': 0, 'prices': []},
        'vip': {'min': float('inf'), 'max': 0, 'count': 0, 'prices': []}
    }
    
    for seat in seats:
        seat_type = seat.type
        price = float(seat.price)
        
        pricing_matrix[seat_type]['prices'].append(price)
        pricing_matrix[seat_type]['count'] += 1
        pricing_matrix[seat_type]['min'] = min(pricing_matrix[seat_type]['min'], price)
        pricing_matrix[seat_type]['max'] = max(pricing_matrix[seat_type]['max'], price)
    
    # Calculate averages
    for seat_type in pricing_matrix:
        if pricing_matrix[seat_type]['count'] > 0:
            prices = pricing_matrix[seat_type]['prices']
            pricing_matrix[seat_type]['avg'] = sum(prices) / len(prices)
        else:
            pricing_matrix[seat_type]['min'] = 0
            pricing_matrix[seat_type]['max'] = 0
            pricing_matrix[seat_type]['avg'] = 0
    
    return {
        'screen': {
            'id': screen.id,
            'name': screen.name
        },
        'pricing': pricing_matrix,
        'total_seats': len(seats)
    }


def apply_dynamic_pricing(screen_id, show_id=None, pricing_rules=None):
    """
    Apply dynamic pricing based on show time, day, or custom rules
    
    Args:
        screen_id (int): ID of the screen
        show_id (int, optional): ID of the show for context
        pricing_rules (dict, optional): Custom pricing rules
        
    Returns:
        dict: Result with updated pricing information
    """
    from app.screens.models import Screen
    from app.shows.models import Show
    
    screen = Screen.query.get(screen_id)
    if not screen:
        return {'success': False, 'message': 'Screen not found'}
    
    show = None
    if show_id:
        show = Show.query.get(show_id)
    
    # Default pricing rules
    default_rules = {
        'weekend_surcharge': 1.2,  # 20% surcharge on weekends
        'matinee_discount': 0.9,   # 10% discount for matinee shows
        'evening_surcharge': 1.1,   # 10% surcharge for evening shows
        'holiday_surcharge': 1.5     # 50% surcharge on holidays
    }
    
    # Merge with custom rules
    if pricing_rules:
        default_rules.update(pricing_rules)
    
    # Get base prices
    seats = Seat.query.filter_by(screen_id=screen_id).all()
    updated_seats = []
    
    for seat in seats:
        base_price = float(seat.price)
        final_price = base_price
        multiplier = 1.0
        
        # Apply show-based pricing
        if show:
            # Weekend surcharge
            if show.is_weekend():
                multiplier *= default_rules['weekend_surcharge']
            
            # Matinee discount
            if show.is_matinee():
                multiplier *= default_rules['matinee_discount']
            
            # Evening surcharge (6PM - 10PM)
            elif show.show_time.hour >= 18 and show.show_time.hour <= 22:
                multiplier *= default_rules['evening_surcharge']
        
        # Apply seat type multiplier
        if seat.type == 'premium':
            multiplier *= 1.5
        elif seat.type == 'vip':
            multiplier *= 2.0
        
        final_price = base_price * multiplier
        final_price = max(final_price, 50.00)  # Minimum price
        
        updated_seats.append({
            'seat_id': seat.id,
            'seat_name': f"{seat.row}{seat.column}",
            'base_price': base_price,
            'final_price': round(final_price, 2),
            'multiplier': round(multiplier, 2),
            'type': seat.type
        })
    
    return {
        'success': True,
        'screen': {
            'id': screen.id,
            'name': screen.name
        },
        'show': {
            'id': show.id if show else None,
            'date': show.show_date.strftime('%Y-%m-%d') if show else None,
            'time': show.show_time.strftime('%H:%M') if show else None
        } if show else None,
        'pricing_rules_applied': default_rules,
        'seats': updated_seats
    }


def get_seat_availability_summary(screen_id, show_id):
    """
    Get comprehensive seat availability summary for a show
    
    Args:
        screen_id (int): ID of the screen
        show_id (int): ID of the show
        
    Returns:
        dict: Detailed availability summary
    """
    from app.screens.models import Screen
    
    screen = Screen.query.get(screen_id)
    if not screen:
        return None
    
    # Get layout with availability
    layout_data = get_seat_layout_with_availability(screen_id, show_id)
    if not layout_data:
        return None
    
    # Calculate statistics
    total_seats = 0
    available_seats = 0
    booked_seats = 0
    locked_seats = 0
    
    availability_by_type = {
        'normal': {'total': 0, 'available': 0, 'booked': 0, 'locked': 0},
        'premium': {'total': 0, 'available': 0, 'booked': 0, 'locked': 0},
        'vip': {'total': 0, 'available': 0, 'booked': 0, 'locked': 0}
    }
    
    for row_letter in layout_data['layout']:
        for col in layout_data['layout'][row_letter]:
            seat = layout_data['layout'][row_letter][col]
            seat_type = seat['type']
            status = seat['status']
            
            total_seats += 1
            availability_by_type[seat_type]['total'] += 1
            
            if status == 'available':
                available_seats += 1
                availability_by_type[seat_type]['available'] += 1
            elif status == 'booked':
                booked_seats += 1
                availability_by_type[seat_type]['booked'] += 1
            elif status == 'locked':
                locked_seats += 1
                availability_by_type[seat_type]['locked'] += 1
    
    # Calculate percentages
    occupancy_rate = (booked_seats + locked_seats) / total_seats * 100 if total_seats > 0 else 0
    
    for seat_type in availability_by_type:
        type_total = availability_by_type[seat_type]['total']
        if type_total > 0:
            availability_by_type[seat_type]['availability_rate'] = (
                availability_by_type[seat_type]['available'] / type_total * 100
            )
            availability_by_type[seat_type]['occupancy_rate'] = (
                (availability_by_type[seat_type]['booked'] + availability_by_type[seat_type]['locked'])
                / type_total * 100
            )
        else:
            availability_by_type[seat_type]['availability_rate'] = 0
            availability_by_type[seat_type]['occupancy_rate'] = 0
    
    return {
        'screen': layout_data['screen'],
        'show_id': show_id,
        'summary': {
            'total_seats': total_seats,
            'available_seats': available_seats,
            'booked_seats': booked_seats,
            'locked_seats': locked_seats,
            'occupancy_rate': round(occupancy_rate, 2)
        },
        'by_type': availability_by_type,
        'layout': layout_data['layout']
    }


def get_seat_utilization_data(start_date, end_date, screen_id=None):
    """
    Get seat utilization data for reports
    
    Args:
        start_date (datetime): Start date for the report
        end_date (datetime): End date for the report
        screen_id (int, optional): ID of the screen to filter by
        
    Returns:
        list: List of utilization data for each screen
    """
    from app.shows.models import Show
    from sqlalchemy import func
    
    # Build base query
    query = db.session.query(
        Screen.id,
        Screen.name,
        func.count(Seat.id).label('total_seats')
    ).join(Seat)
    
    # Filter by screen if provided
    if screen_id:
        query = query.filter(Screen.id == screen_id)
    
    # Group by screen
    screens_data = query.group_by(Screen.id, Screen.name).all()
    
    utilization_data = []
    
    for screen_id, screen_name, total_seats in screens_data:
        # Get shows for this screen in the date range
        shows = Show.query.filter(
            Show.screen_id == screen_id,
            Show.show_date >= start_date.date(),
            Show.show_date <= end_date.date(),
            Show.status.in_(['scheduled', 'completed'])
        ).all()
        
        # Calculate total capacity (seats × shows)
        total_capacity = total_seats * len(shows) if shows else 0
        
        # Get booked seats for all shows
        from app.bookings.models import BookingSeat
        from app.bookings.models import Booking
        booked_seats = db.session.query(func.count(BookingSeat.id)).join(Booking).join(Show).filter(
            Show.screen_id == screen_id,
            Show.show_date >= start_date.date(),
            Show.show_date <= end_date.date(),
            Booking.status == 'confirmed'
        ).scalar() or 0
        
        # Calculate utilization
        utilization_rate = (booked_seats / total_capacity * 100) if total_capacity > 0 else 0
        available_seats = total_capacity - booked_seats
        
        utilization_data.append({
            'screen_id': screen_id,
            'screen_name': screen_name,
            'total_seats': total_seats,
            'total_capacity': total_capacity,
            'booked_seats': booked_seats,
            'available_seats': available_seats,
            'utilization_rate': round(utilization_rate, 2)
        })
    
    return utilization_data


def get_seat_type_performance(start_date, end_date, screen_id=None):
    """
    Get seat type performance data for reports
    
    Args:
        start_date (datetime): Start date for the report
        end_date (datetime): End date for the report
        screen_id (int, optional): ID of the screen to filter by
        
    Returns:
        list: List of performance data for each seat type
    """
    from app.shows.models import Show
    from sqlalchemy import func
    
    # Build base query for seats by type
    seat_query = db.session.query(
        Seat.type,
        func.count(Seat.id).label('total_seats')
    )
    
    # Filter by screen if provided
    if screen_id:
        seat_query = seat_query.filter(Seat.screen_id == screen_id)
    
    # Group by seat type
    seat_data = seat_query.group_by(Seat.type).all()
    
    performance_data = []
    
    for seat_type, total_seats in seat_data:
        # Get shows in the date range
        shows_query = Show.query.filter(
            Show.show_date >= start_date.date(),
            Show.show_date <= end_date.date(),
            Show.status.in_(['scheduled', 'completed'])
        )
        
        if screen_id:
            shows_query = shows_query.filter(Show.screen_id == screen_id)
        
        shows = shows_query.all()
        
        # Calculate total capacity
        total_capacity = total_seats * len(shows) if shows else 0
        
        # Get booked seats for this type
        booked_query = db.session.query(func.count(BookingSeat.id)).join(Booking).join(Show).join(Seat).filter(
            Seat.type == seat_type,
            Show.show_date >= start_date.date(),
            Show.show_date <= end_date.date(),
            Booking.status == 'confirmed'
        )
        
        if screen_id:
            booked_query = booked_query.filter(Show.screen_id == screen_id)
        
        booked_seats = booked_query.scalar() or 0
        
        # Calculate utilization
        utilization_rate = (booked_seats / total_capacity * 100) if total_capacity > 0 else 0
        available_seats = total_capacity - booked_seats
        
        performance_data.append({
            'seat_type': seat_type,
            'total_seats': total_seats,
            'total_capacity': total_capacity,
            'booked_seats': booked_seats,
            'available_seats': available_seats,
            'utilization_rate': round(utilization_rate, 2)
        })
    
    return performance_data