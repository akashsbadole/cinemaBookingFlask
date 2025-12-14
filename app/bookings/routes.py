"""
Booking Routes
"""
from app.search import BookingSearch, SearchAnalytics, get_search_params_from_request
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, make_response, send_file, abort
from flask_login import login_required, current_user
from app.bookings import bp
from app.bookings.forms import BookingForm, ShowSelectionForm, BookingSearchForm, AdvancedBookingSearchForm
from app.bookings.models import Booking, BookingSeat
from app.bookings.utils import generate_qr_code, get_available_seats, validate_booking_rules
from app.movies.models import Movie
from app.shows.models import Show
from app.screens.models import Screen, Seat
from app.error_handlers import ErrorLogger, ErrorHandler
from app.validators import SecurityValidator, InputSanitizer, DataValidators
from app.utils_audit import ConcurrentAccessChecker
from app.database import db
from datetime import datetime, timedelta
from wtforms import ValidationError
import logging
import io
import qrcode

# Import seat management utilities
from app.screens.utils import (
    get_seat_layout_with_availability,
    lock_seats_for_booking, release_seat_locks, check_seat_availability
)
from app.screens.models import SeatLock

class BookingCalculator:
    @staticmethod
    def calculate_booking_cost(show_id, seat_ids):
        """Calculate booking cost based on seat types and show pricing"""
        from app.screens.models import Seat
        from app.shows.models import Show
        
        show = Show.query.get(show_id)
        if not show:
            return 0, []
        
        total_cost = 0.0
        seat_costs = []
        
        for seat_id in seat_ids:
            seat = Seat.query.get(seat_id)
            if not seat:
                continue
                
            # Calculate price with dynamic pricing
            base_price = float(seat.price)
            
            # Apply show-specific pricing
            if show.weekend_surcharge and show.show_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
                base_price *= (1 + float(show.weekend_surcharge) / 100)
            
            if show.matinee_discount and show.show_time.hour < 17:  # Before 5 PM
                base_price *= (1 - float(show.matinee_discount) / 100)
            
            # Apply seat type multipliers
            if seat.type == 'premium':
                base_price *= 1.5
            elif seat.type == 'vip':
                base_price *= 2.0
            
            seat_costs.append({
                'seat_id': seat_id,
                'price': round(base_price, 2),
                'seat_type': seat.type,
                'seat_number': seat.seat_number
            })
            total_cost += base_price
        
        return round(total_cost, 2), seat_costs
    
    @staticmethod
    def get_price_breakdown(show_id, seat_ids):
        """Get detailed price breakdown"""
        from app.screens.models import Seat
        from app.shows.models import Show
        
        show = Show.query.get(show_id)
        if not show:
            return {'base_price': 0, 'total': 0, 'seat_count': 0}
        
        # Get seat type counts
        seat_type_counts = {'normal': 0, 'premium': 0, 'vip': 0}
        base_price = float(show.base_price) if show.base_price else 150.0
        
        for seat_id in seat_ids:
            seat = Seat.query.get(seat_id)
            if seat:
                seat_type_counts[seat.type] += 1
        
        # Calculate totals by type
        normal_total = seat_type_counts['normal'] * base_price
        premium_total = seat_type_counts['premium'] * base_price * 1.5
        vip_total = seat_type_counts['vip'] * base_price * 2.0
        
        # Apply show-specific adjustments
        total = normal_total + premium_total + vip_total
        if show.weekend_surcharge and show.show_date.weekday() >= 5:
            total *= (1 + float(show.weekend_surcharge) / 100)
        
        if show.matinee_discount and show.show_time.hour < 17:
            total *= (1 - float(show.matinee_discount) / 100)
        
        return {
            'base_price': base_price,
            'total': round(total, 2),
            'seat_count': len(seat_ids),
            'seat_type_counts': seat_type_counts,
            'type_totals': {
                'normal': round(normal_total, 2),
                'premium': round(premium_total, 2),
                'vip': round(vip_total, 2)
            }
        }

# Add admin_required decorator
def admin_required(f):
    """Decorator to require admin privileges"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For now, just pass through - in real implementation, check user role
        return f(*args, **kwargs)
    return decorated_function

logger = logging.getLogger(__name__)

@bp.route('/new/<int:show_id>', methods=['GET', 'POST'])
@login_required
def new_booking(show_id):
    """Create new booking for a show"""
    try:
        show = Show.query.get(show_id)
        if not show:
            flash('Show not found', 'danger')
            return redirect(url_for('movies.index'))
        
        # Check if show is available for booking
        if not show.is_available_for_booking():
            flash('This show is no longer available for booking', 'danger')
            return redirect(url_for('shows.view_show', show_id=show_id))
        
        # Get available seats
        available_seats = get_available_seats(show_id)
        
        # Create booking form
        form = BookingForm()
        form.show_id.data = show_id
        
        return render_template('bookings/new.html', title='New Booking',
                             form=form, show=show, available_seats=available_seats)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while initializing booking', 'danger')
        return redirect(url_for('movies.index'))

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    """List all bookings with search and filtering"""
    try:
        # Get search parameters using centralized utility
        params = get_search_params_from_request(request, [
            'search', 'search_type', 'date_from', 'date_to', 'booking_status', 'payment_status',
            'payment_method', 'amount_min', 'amount_max', 'show_id', 'customer_email',
            'customer_phone', 'seat_number', 'sort_by', 'page', 'per_page'
        ])
        
        # Create search form
        search_form = BookingSearchForm()
        
        # Use BookingSearch from centralized utility
        booking_search = BookingSearch()
        
        # Apply search parameters
        if params.get('search'):
            booking_search.set_search_term(params['search'])
        
        if params.get('search_type'):
            booking_search.set_search_type(params['search_type'])
        
        if params.get('date_from'):
            booking_search.set_date_range(params['date_from'], params.get('date_to'))
        
        if params.get('booking_status'):
            booking_search.set_booking_status(params['booking_status'])
        
        if params.get('payment_status'):
            booking_search.set_payment_status(params['payment_status'])
        
        if params.get('payment_method'):
            booking_search.set_payment_method(params['payment_method'])
        
        if params.get('amount_min') or params.get('amount_max'):
            booking_search.set_amount_range(params.get('amount_min'), params.get('amount_max'))
        
        if params.get('show_id'):
            booking_search.set_show_id(params['show_id'])
        
        if params.get('customer_email'):
            booking_search.set_customer_email(params['customer_email'])
        
        if params.get('customer_phone'):
            booking_search.set_customer_phone(params['customer_phone'])
        
        if params.get('seat_number'):
            booking_search.set_seat_number(params['seat_number'])
        
        if params.get('sort_by'):
            booking_search.set_sort_by(params['sort_by'])
        
        # Set pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 20)
        booking_search.set_pagination(page, per_page)
        
        # Execute search
        search_result = booking_search.execute()
        
        # Track search analytics
        try:
            analytics = SearchAnalytics()
            analytics.track_search(
                user_id=current_user.id,
                module='bookings',
                search_term=params.get('search', ''),
                filters=params,
                result_count=search_result['total']
            )
        except Exception as e:
            # Log analytics error but don't fail the search
            ErrorLogger.log_error(e, request, context={'analytics_error': True})
        
        return render_template('bookings/index.html',
                             title='Bookings',
                             bookings=search_result['items'],
                             search_form=search_form,
                             pagination=search_result['pagination'],
                             search_params=params)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading bookings', 'danger')
        return render_template('bookings/index.html',
                             title='Bookings',
                             bookings=[],
                             search_form=BookingSearchForm())

@bp.route('/new')
@login_required
def new():
    """Create new booking - first step: select show"""
    try:
        # Clean up expired locks first
        SeatLock.release_expired_locks()
        
        # Get form for show selection
        form = ShowSelectionForm()
        
        return render_template('bookings/select_show.html', title='Select Show', form=form)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while initializing booking', 'danger')
        return redirect(url_for('index'))

@bp.route('/advanced_search')
@login_required
def advanced_search():
    """Advanced search page for bookings"""
    try:
        # Create advanced search form
        form = AdvancedBookingSearchForm()
        
        # Pre-fill form with current search parameters if coming from main search
        params = get_search_params_from_request(request, [
            'search', 'search_type', 'date_from', 'date_to', 'booking_status', 'payment_status',
            'payment_method', 'amount_min', 'amount_max', 'show_id', 'customer_email',
            'customer_phone', 'seat_number', 'sort_by', 'page', 'per_page'
        ])
        
        # Populate form with existing parameters
        for key, value in params.items():
            if hasattr(form, key) and value:
                getattr(form, key).data = value
        
        return render_template('bookings/advanced_search.html',
                             title='Advanced Booking Search',
                             form=form,
                             search_params=params)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading advanced search', 'danger')
        return redirect(url_for('bookings.index'))

@bp.route('/select_show', methods=['POST'])
@login_required
def select_show():
    """Process show selection and redirect to seat selection"""
    form = ShowSelectionForm()
    
    try:
        if form.validate_on_submit():
            # Validate and sanitize form inputs
            movie_id = int(form.movie_id.data) if form.movie_id.data and form.movie_id.data != 0 else None
            screen_id = int(form.screen_id.data) if form.screen_id.data and form.screen_id.data != 0 else None
            
            date_int = form.show_date.data
            show_date = None
            if date_int and date_int != 0:
                try:
                    show_date = datetime.strptime(str(date_int), '%Y%m%d').date()
                except ValueError:
                    raise ValidationError("Invalid date format")
            
            # Build show query based on filters
            query = Show.query.join(Movie).filter(Movie.status == 'active').join(Screen)
            
            if movie_id:
                query = query.filter(Show.movie_id == movie_id)
            
            if screen_id:
                query = query.filter(Show.screen_id == screen_id)
            
            if show_date:
                query = query.filter(Show.show_date == show_date)
            
            # Only get future shows
            query = query.filter(
                Show.show_date >= datetime.now().date(),
                Show.status == 'scheduled'
            ).order_by(Show.show_date, Show.show_time)
            
            shows = query.all()
            
            if not shows:
                flash('No shows found matching your criteria', 'info')
                return render_template('bookings/show_list.html', title='Available Shows', 
                                     shows=[], form=form)
            
            return render_template('bookings/show_list.html', title='Available Shows', 
                                 shows=shows, form=form)
        
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'danger')
        
        return redirect(url_for('bookings.new'))
    
    except ValidationError as e:
        flash(str(e), 'danger')
        return redirect(url_for('bookings.new'))
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while searching for shows', 'danger')
        return redirect(url_for('bookings.new'))

@bp.route('/show/<int:show_id>/seats')
@login_required
def select_seats(show_id):
    """Seat selection page with enhanced validation"""
    try:
        # Validate show_id
        if show_id <= 0:
            flash('Invalid show ID', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Clean up expired locks
        SeatLock.release_expired_locks()
        
        # Get show details
        show = Show.query.get(show_id)
        if not show:
            flash('Show not found', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Validate show is in the future and not ended
        now = datetime.now()
        show_datetime = datetime.combine(show.show_date, 
                                       datetime.strptime(str(show.show_time), '%H:%M:%S').time())
        
        if show_datetime <= now:
            flash('This show has already started or is in the past', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Validate show status
        if show.status != 'scheduled':
            flash('This show is not currently available for booking', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Get seat layout with availability
        layout_data = get_seat_layout_with_availability(show.screen_id, show_id)
        if not layout_data:
            flash('Unable to load seat layout', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Convert to expected format for template
        seat_layout = {
            'layout': [],
            'rows': layout_data['screen']['total_rows'],
            'seats_per_row': layout_data['screen']['total_columns']
        }
        
        # Convert layout data to expected format
        for row_letter in layout_data['layout']:
            for col in layout_data['layout'][row_letter]:
                seat = layout_data['layout'][row_letter][col]
                seat_layout['layout'].append({
                    'row': seat['row'],
                    'number': seat['column'],
                    'status': seat['status'],
                    'type': seat['type']
                })
        
        # Validate seat layout
        if not seat_layout or 'layout' not in seat_layout:
            flash('Unable to load seat layout', 'danger')
            return redirect(url_for('bookings.new'))
        
        # Get pricing information with validation
        try:
            base_price = float(show.base_price) if show.base_price else 0
            weekend_surcharge = float(show.weekend_surcharge or 0) if show.is_weekend() else 0
            matinee_discount = float(show.matinee_discount or 0) if show.is_matinee() else 0
            
            price_info = {
                'base_price': base_price,
                'weekend_surcharge': weekend_surcharge,
                'matinee_discount': matinee_discount,
                'is_weekend': show.is_weekend(),
                'is_matinee': show.is_matinee()
            }
            
            # Validate pricing
            if base_price < 0:
                raise ValidationError("Invalid base price")
            if weekend_surcharge < 0:
                raise ValidationError("Invalid weekend surcharge")
            if matinee_discount < 0:
                raise ValidationError("Invalid matinee discount")
            
        except (ValueError, ValidationError) as e:
            ErrorLogger.log_error(e, request, context={'show_id': show_id})
            flash('Invalid pricing information for this show', 'danger')
            return redirect(url_for('bookings.new'))
        
        return render_template('bookings/select_seats.html', title='Select Seats',
                             show=show, seat_layout=seat_layout, price_info=price_info)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'show_id': show_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading seat selection', 'danger')
        return redirect(url_for('bookings.new'))

@bp.route('/api/show/<int:show_id>/seat_status')
@login_required
def api_seat_status(show_id):
    """API endpoint to get current seat status with validation"""
    try:
        # Validate show_id
        if show_id <= 0:
            return jsonify({'success': False, 'error': 'Invalid show ID'})
        
        # Clean up expired locks first
        SeatLock.release_expired_locks()
        
        # Validate show exists and is bookable
        show = Show.query.get(show_id)
        if not show:
            return jsonify({'success': False, 'error': 'Show not found'})
        
        if show.status != 'scheduled':
            return jsonify({'success': False, 'error': 'Show is not available for booking'})
        
        # Check if show is still in the future
        show_datetime = datetime.combine(show.show_date, 
                                       datetime.strptime(str(show.show_time), '%H:%M:%S').time())
        if show_datetime <= datetime.now():
            return jsonify({'success': False, 'error': 'Show has already started'})
        
        layout_data = get_seat_layout_with_availability(show.screen_id, show_id)
        
        # Convert to expected format
        seat_layout = {
            'layout': [],
            'rows': layout_data['screen']['total_rows'],
            'seats_per_row': layout_data['screen']['total_columns']
        }
        
        # Convert layout data to expected format
        for row_letter in layout_data['layout']:
            for col in layout_data['layout'][row_letter]:
                seat = layout_data['layout'][row_letter][col]
                seat_layout['layout'].append({
                    'row': seat['row'],
                    'number': seat['column'],
                    'status': seat['status'],
                    'type': seat['type']
                })
        
        # Validate seat layout
        if not seat_layout or 'layout' not in seat_layout:
            return jsonify({'success': False, 'error': 'Unable to load seat layout'})
        
        return jsonify({'success': True, 'seat_layout': seat_layout})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'show_id': show_id})
        return jsonify({'success': False, 'error': 'Failed to get seat status'})

@bp.route('/api/lock_seats', methods=['POST'])
@login_required
def api_lock_seats():
    """API endpoint to lock seats temporarily with enhanced validation"""
    try:
        # Get and validate JSON data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'})
        
        # Sanitize and validate inputs
        show_id = int(data.get('show_id', 0))
        seat_ids = data.get('seat_ids', [])
        duration = int(data.get('duration_minutes', 5))
        
        # Validate inputs
        if show_id <= 0:
            return jsonify({'success': False, 'error': 'Invalid show ID'})
        
        if not seat_ids or not isinstance(seat_ids, list) or len(seat_ids) == 0:
            return jsonify({'success': False, 'error': 'Seat IDs are required'})
        
        # Validate seat IDs
        try:
            seat_ids = [int(sid) for sid in seat_ids]
            if any(sid <= 0 for sid in seat_ids):
                return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        
        # Validate duration
        if duration <= 0 or duration > 30:  # Max 30 minutes
            return jsonify({'success': False, 'error': 'Lock duration must be between 1 and 30 minutes'})
        
        # Validate show exists and is bookable
        show = Show.query.get(show_id)
        if not show:
            return jsonify({'success': False, 'error': 'Show not found'})
        
        if show.status != 'scheduled':
            return jsonify({'success': False, 'error': 'Show is not available for booking'})
        
        # Check for concurrent access conflicts
        conflict_check = ConcurrentAccessChecker.check_booking_conflicts(show_id, seat_ids, current_user.id)
        if conflict_check['has_conflict']:
            ErrorLogger.log_security_event(
                'seat_lock_conflict',
                f'Seat lock conflict detected for show {show_id}',
                request,
                user_id=current_user.id,
                context={'seat_ids': seat_ids, 'conflicts': conflict_check['conflicts']}
            )
            return jsonify({'success': False, 'error': 'Seats are already being booked by other users'})
        
        # Validate seat availability
        for seat_id in seat_ids:
            availability = check_seat_availability(seat_id, show_id)
            if not availability['available']:
                return jsonify({
                    'success': False,
                    'error': f"Seat {availability['seat'].seat_number} is not available: {availability['reason']}"
                })
        
        # Lock seats
        result = lock_seats_for_booking(seat_ids, show_id, current_user.id, duration)
        locked_seats = result.get('locked_seats', [])
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': 'Failed to lock seats',
                'details': result.get('errors', [])
            })
        
        ErrorLogger.log_security_event(
            'seats_locked',
            f'User {current_user.username} locked {len(locked_seats)} seats for show {show_id}',
            request,
            user_id=current_user.id,
            context={'show_id': show_id, 'seat_ids': seat_ids, 'duration': duration}
        )
        
        return jsonify({
            'success': True,
            'message': f'{len(locked_seats)} seats locked for {duration} minutes',
            'lock_expiry': (datetime.utcnow() + timedelta(minutes=duration)).isoformat()
        })
    
    except ValueError as e:
        return jsonify({'success': False, 'error': 'Invalid data format'})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        return jsonify({'success': False, 'error': 'Failed to lock seats'})

@bp.route('/api/release_seats', methods=['POST'])
@login_required
def api_release_seats():
    """API endpoint to release seat locks with validation"""
    try:
        # Get and validate JSON data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'})
        
        # Sanitize and validate inputs
        show_id = int(data.get('show_id', 0))
        seat_ids = data.get('seat_ids', [])
        
        # Validate inputs
        if show_id <= 0:
            return jsonify({'success': False, 'error': 'Invalid show ID'})
        
        if not seat_ids or not isinstance(seat_ids, list) or len(seat_ids) == 0:
            return jsonify({'success': False, 'error': 'Seat IDs are required'})
        
        # Validate seat IDs
        try:
            seat_ids = [int(sid) for sid in seat_ids]
            if any(sid <= 0 for sid in seat_ids):
                return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        
        # Validate show exists
        show = Show.query.get(show_id)
        if not show:
            return jsonify({'success': False, 'error': 'Show not found'})
        
        released_count = release_seat_locks(seat_ids, show_id, current_user.id)
        
        ErrorLogger.log_security_event(
            'seats_released',
            f'User {current_user.username} released {released_count} seats for show {show_id}',
            request,
            user_id=current_user.id,
            context={'show_id': show_id, 'seat_ids': seat_ids}
        )
        
        return jsonify({
            'success': True,
            'message': f'{released_count} seats released'
        })
    
    except ValueError as e:
        return jsonify({'success': False, 'error': 'Invalid data format'})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        return jsonify({'success': False, 'error': 'Failed to release seats'})

@bp.route('/api/calculate_price', methods=['POST'])
@login_required
def api_calculate_price():
    """API endpoint to calculate booking price with enhanced validation"""
    try:
        # Get and validate JSON data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Invalid JSON data'})
        
        # Sanitize and validate inputs
        show_id = int(data.get('show_id', 0))
        seat_ids = data.get('seat_ids', [])
        
        # Validate inputs
        if show_id <= 0:
            return jsonify({'success': False, 'error': 'Invalid show ID'})
        
        if not seat_ids or not isinstance(seat_ids, list) or len(seat_ids) == 0:
            return jsonify({'success': False, 'error': 'Seat IDs are required'})
        
        # Validate seat IDs
        try:
            seat_ids = [int(sid) for sid in seat_ids]
            if any(sid <= 0 for sid in seat_ids):
                return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid seat ID format'})
        
        # Validate maximum seats per booking
        if len(seat_ids) > 10:  # Max 10 seats per booking
            return jsonify({'success': False, 'error': 'Maximum 10 seats allowed per booking'})
        
        # Validate show exists
        show = Show.query.get(show_id)
        if not show:
            return jsonify({'success': False, 'error': 'Show not found'})
        
        # Validate show is bookable
        if show.status != 'scheduled':
            return jsonify({'success': False, 'error': 'Show is not available for booking'})
        
        # Calculate total cost
        total_cost, seat_costs = BookingCalculator.calculate_booking_cost(show_id, seat_ids)
        
        # Validate pricing
        if total_cost < 0:
            return jsonify({'success': False, 'error': 'Invalid price calculation'})
        
        price_details = BookingCalculator.get_price_breakdown(show_id, seat_ids)
        
        return jsonify({
            'success': True,
            'total_cost': float(total_cost),
            'seat_count': len(seat_ids),
            'breakdown': price_details
        })
    
    except ValueError as e:
        return jsonify({'success': False, 'error': 'Invalid data format'})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        return jsonify({'success': False, 'error': 'Failed to calculate price'})

@bp.route('/confirm_booking', methods=['GET', 'POST'])
@login_required
def confirm_booking():
    """Confirm and create booking with enhanced validation"""
    if request.method == 'GET':
        try:
            # Get and sanitize booking details from query parameters
            show_id = request.args.get('show_id', type=int)
            seat_ids_str = request.args.get('seat_ids', '')
            
            # Validate inputs
            if not show_id or show_id <= 0:
                flash('Invalid show ID', 'danger')
                return redirect(url_for('bookings.new'))
            
            if not seat_ids_str:
                flash('Invalid seat selection', 'danger')
                return redirect(url_for('bookings.new'))
            
            # Validate and parse seat IDs
            try:
                seat_ids = [int(sid) for sid in seat_ids_str.split(',') if sid.strip()]
                if not seat_ids or any(sid <= 0 for sid in seat_ids):
                    raise ValueError("Invalid seat ID format")
            except ValueError:
                flash('Invalid seat IDs', 'danger')
                return redirect(url_for('bookings.new'))
            
            # Validate maximum seats per booking
            if len(seat_ids) > 10:
                flash('Maximum 10 seats allowed per booking', 'danger')
                return redirect(url_for('bookings.select_seats', show_id=show_id))
            
            # Validate show exists
            show = Show.query.get(show_id)
            if not show:
                flash('Show not found', 'danger')
                return redirect(url_for('bookings.new'))
            
            # Validate show is bookable
            if show.status != 'scheduled':
                flash('This show is not available for booking', 'danger')
                return redirect(url_for('bookings.select_seats', show_id=show_id))
            
            # Validate show is still in the future
            show_datetime = datetime.combine(show.show_date, 
                                           datetime.strptime(str(show.show_time), '%H:%M:%S').time())
            if show_datetime <= datetime.now():
                flash('This show has already started', 'danger')
                return redirect(url_for('bookings.new'))
            
            # Validate seat availability
            for seat_id in seat_ids:
                availability = check_seat_availability(seat_id, show_id)
                if not availability['available']:
                    flash(f"Seat {availability['seat'].row}{availability['seat'].column} is not available: {availability['reason']}", 'danger')
                    return redirect(url_for('bookings.select_seats', show_id=show_id))
            
            # Calculate and validate total cost
            total_cost, seat_costs = BookingCalculator.calculate_booking_cost(show_id, seat_ids)
            if total_cost < 0:
                flash('Invalid price calculation', 'danger')
                return redirect(url_for('bookings.new'))
            
            # Create booking form
            form = BookingForm()
            form.show_id.data = show_id
            form.total_amount.data = total_cost
            
            return render_template('bookings/confirm_booking.html',
                                 title='Confirm Booking', form=form,
                                 show=show, seat_costs=seat_costs,
                                 total_amount=total_cost, seat_ids=seat_ids)
        
        except Exception as e:
            ErrorLogger.log_error(e, request, user_id=current_user.id)
            ErrorHandler.handle_error(e, request)
            flash('An error occurred while preparing the booking', 'danger')
            return redirect(url_for('bookings.new'))
    
    else:  # POST
        form = BookingForm()
        
        try:
            if form.validate_on_submit():
                # Get and sanitize seat IDs from form
                seat_ids_str = request.form.get('seat_ids', '')
                if not seat_ids_str:
                    flash('No seats selected', 'danger')
                    return redirect(url_for('bookings.new'))
                
                # Validate and parse seat IDs
                try:
                    seat_ids = [int(sid) for sid in seat_ids_str.split(',') if sid.strip()]
                    if not seat_ids or any(sid <= 0 for sid in seat_ids):
                        raise ValueError("Invalid seat ID format")
                except ValueError:
                    flash('Invalid seat IDs', 'danger')
                    return redirect(url_for('bookings.new'))
                
                # Sanitize customer data
                customer_name = InputSanitizer.sanitize_string(form.customer_name.data, max_length=100)
                customer_phone = InputSanitizer.sanitize_string(form.customer_phone.data, max_length=20)
                customer_email = InputSanitizer.sanitize_email(form.customer_email.data)
                payment_method = InputSanitizer.sanitize_string(form.payment_method.data, max_length=20)
                payment_reference = InputSanitizer.sanitize_string(form.payment_reference.data, max_length=100)
                
                # Security checks
                if SecurityValidator.detect_sql_injection([customer_name, customer_phone, customer_email]):
                    ErrorLogger.log_security_event(
                        'sql_injection_attempt',
                        f'SQL injection attempt detected in booking confirmation',
                        request,
                        user_id=current_user.id,
                        severity='high'
                    )
                    abort(400, "Invalid input detected")
                
                # Validate customer data
                if not DataValidators.validate_name_format(customer_name):
                    raise ValidationError("Invalid customer name format")
                
                if customer_phone and not DataValidators.validate_phone_format(customer_phone):
                    raise ValidationError("Invalid phone number format")
                
                if customer_email and not DataValidators.validate_email_format(customer_email):
                    raise ValidationError("Invalid email format")
                
                # Validate payment method
                valid_payment_methods = ['cash', 'card', 'upi', 'net_banking']
                if payment_method not in valid_payment_methods:
                    raise ValidationError("Invalid payment method")
                
                # Validate show and final availability
                show_id = int(form.show_id.data)
                show = Show.query.get(show_id)
                if not show:
                    raise ValidationError("Show not found")
                
                # Final validation of seat availability
                for seat_id in seat_ids:
                    availability = check_seat_availability(seat_id, show_id)
                    if not availability['available']:
                        raise ValidationError(f"Seat {availability['seat'].row}{availability['seat'].column} is not available: {availability['reason']}")
                
                # Calculate final cost
                total_cost, seat_costs = BookingCalculator.calculate_booking_cost(show_id, seat_ids)
                
                # Validate amount consistency
                if abs(float(total_cost) - float(form.total_amount.data)) > 0.01:
                    ErrorLogger.log_security_event(
                        'booking_price_mismatch',
                        f'Price mismatch in booking confirmation. Expected: {total_cost}, Received: {form.total_amount.data}',
                        request,
                        user_id=current_user.id,
                        severity='high'
                    )
                    raise ValidationError("Price mismatch detected")
                
                # Create booking with validation
                booking = Booking(
                    show_id=show_id,
                    user_id=current_user.id,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    customer_email=customer_email,
                    total_amount=total_cost,
                    payment_method=payment_method,
                    payment_reference=payment_reference,
                    booking_time=datetime.utcnow()
                )
                
                # Generate reference number
                booking.generate_reference_number()
                
                # Add to session
                db.session.add(booking)
                db.session.flush()  # Get the booking ID
                
                # Create booking seats and release any existing locks
                for i, seat_id in enumerate(seat_ids):
                    # Find and remove any existing locks for this seat
                    existing_locks = db.session.query(BookingSeat).join(Booking).filter(
                        BookingSeat.seat_id == seat_id,
                        Booking.show_id == show_id,
                        BookingSeat.status == 'locked',
                        Booking.status == 'pending'
                    ).all()
                    
                    for lock in existing_locks:
                        db.session.delete(lock)
                    
                    # Create the actual booking seat with validation
                    seat_price = seat_costs[i]['price'] if i < len(seat_costs) else 0
                    if seat_price < 0:
                        raise ValidationError("Invalid seat price")
                    
                    booking_seat = BookingSeat(
                        booking_id=booking.id,
                        seat_id=seat_id,
                        status='booked',
                        price=seat_price
                    )
                    db.session.add(booking_seat)
                
                # Confirm the booking
                booking.confirm_booking()
                
                # Create payment record
                from app.payments.models import Payment
                payment = Payment(
                    booking_id=booking.id,
                    amount=total_cost,
                    mode=payment_method,
                    reference_id=payment_reference,
                    status='completed',
                    completed_at=datetime.utcnow()
                )
                db.session.add(payment)
                
                # Commit transaction
                db.session.commit()
                
                ErrorLogger.log_security_event(
                    'booking_created',
                    f'User {current_user.username} created booking {booking.reference_number}',
                    request,
                    user_id=current_user.id,
                    context={
                        'booking_id': booking.id,
                        'show_id': show_id,
                        'seat_ids': seat_ids,
                        'amount': total_cost
                    }
                )
                
                flash(f'Booking confirmed! Reference: {booking.reference_number}', 'success')
                return redirect(url_for('payments.process', booking_id=booking.id))
            
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{getattr(form, field).label.text}: {error}', 'danger')
            
            # Re-render form with data
            show_id = int(form.show_id.data) if form.show_id.data else 0
            seat_ids_str = request.form.get('seat_ids', '')
            
            try:
                seat_ids = [int(sid) for sid in seat_ids_str.split(',') if sid.strip()]
                if show_id > 0 and seat_ids:
                    total_cost, seat_costs = BookingCalculator.calculate_booking_cost(show_id, seat_ids)
                    show = Show.query.get(show_id)
                    
                    return render_template('bookings/confirm_booking.html', 
                                         title='Confirm Booking', form=form, 
                                         show=show, seat_costs=seat_costs,
                                         total_amount=total_cost, seat_ids=seat_ids)
            except Exception:
                pass
            
            return redirect(url_for('bookings.new'))
        
        except ValidationError as e:
            db.session.rollback()
            ErrorLogger.log_security_event(
                'booking_validation_error',
                f'Validation error in booking confirmation: {str(e)}',
                request,
                user_id=current_user.id,
                severity='medium'
            )
            flash(str(e), 'danger')
            return redirect(url_for('bookings.new'))
        
        except Exception as e:
            db.session.rollback()
            ErrorLogger.log_error(e, request, user_id=current_user.id)
            ErrorHandler.handle_error(e, request)
            flash('An error occurred while creating the booking', 'danger')
            return redirect(url_for('bookings.new'))

@bp.route('/view/<int:id>')
@login_required
def view(id):
    """View booking details with validation"""
    try:
        if id <= 0:
            flash('Invalid booking ID', 'danger')
            return redirect(url_for('bookings.index'))
        
        booking = Booking.query.get(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        # Get seats for this booking
        booking.seats_list = booking.get_seats_list()
        booking.seats = ', '.join(booking.seats_list)
        
        return render_template('bookings/view.html', title='Booking Details', booking=booking)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading booking details', 'danger')
        return redirect(url_for('bookings.index'))

@bp.route('/ticket/<int:id>')
@login_required
def ticket(id):
    """View ticket for printing with validation"""
    try:
        if id <= 0:
            flash('Invalid booking ID', 'danger')
            return redirect(url_for('bookings.index'))
        
        booking = Booking.query.get(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        # Get seats for this booking
        booking.seats_list = booking.get_seats_list()
        booking.seats = ', '.join(booking.seats_list)
        
        return render_template('bookings/ticket.html', title='Movie Ticket', booking=booking)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while generating ticket', 'danger')
        return redirect(url_for('bookings.index'))

@bp.route('/ticket/<int:id>/qr')
@login_required
def ticket_qr(id):
    """Generate QR code for ticket with validation"""
    try:
        if id <= 0:
            return jsonify({'error': 'Invalid booking ID'}), 400
        
        booking = Booking.query.get(id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Sanitize QR code data
        customer_name = InputSanitizer.sanitize_string(booking.customer_name, max_length=50)
        movie_title = InputSanitizer.sanitize_string(booking.show.movie.title, max_length=100)
        seats_list = booking.get_seats_list()
        
        # Generate QR code with booking information
        qr_data = f"Booking Ref: {booking.reference_number}\nCustomer: {customer_name}\nMovie: {movie_title}\nDate: {booking.show.show_date}\nTime: {booking.show.show_time}\nSeats: {', '.join(seats_list)}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        return jsonify({'error': 'Failed to generate QR code'}), 500

@bp.route('/ticket/<int:id>/pdf')
@login_required
def ticket_pdf(id):
    """Generate PDF ticket with validation"""
    try:
        if id <= 0:
            return jsonify({'error': 'Invalid booking ID'}), 400
        
        booking = Booking.query.get(id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Prepare and sanitize booking data for PDF generation
        booking_data = {
            'id': booking.id,
            'reference_number': booking.reference_number,
            'customer_name': InputSanitizer.sanitize_string(booking.customer_name, max_length=100),
            'movie_title': InputSanitizer.sanitize_string(booking.show.movie.title, max_length=200) if booking.show.movie else 'N/A',
            'screen_name': InputSanitizer.sanitize_string(booking.show.screen.name, max_length=100) if booking.show.screen else 'N/A',
            'show_date': booking.show.show_date.strftime('%d %b %Y') if booking.show.show_date else 'N/A',
            'show_time': booking.show.show_time.strftime('%I:%M %p') if booking.show.show_time else 'N/A',
            'seats': ', '.join(booking.get_seats_list()),
            'total_amount': float(booking.total_amount) if booking.total_amount else 0
        }
        
        # Generate PDF
        pdf_data = generate_ticket_pdf(booking_data)
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=ticket_{booking.reference_number}.pdf'
        
        return response
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        ErrorHandler.handle_error(e, request)
        return jsonify({'error': 'Failed to generate PDF ticket'}), 500

@bp.route('/cancel/<int:id>', methods=['POST'])
@login_required
@admin_required
def cancel(id):
    """Cancel booking with validation and audit logging"""
    try:
        if id <= 0:
            flash('Invalid booking ID', 'danger')
            return redirect(url_for('bookings.index'))
        
        booking = Booking.query.get(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        if booking.status == 'cancelled':
            flash('Booking is already cancelled', 'warning')
            return redirect(url_for('bookings.view', id=id))
        
        # Validate booking can be cancelled (not too old)
        if booking.booking_time < datetime.utcnow() - timedelta(days=7):
            flash('Bookings older than 7 days cannot be cancelled', 'danger')
            return redirect(url_for('bookings.view', id=id))
        
        booking.cancel_booking()
        db.session.commit()
        
        ErrorLogger.log_security_event(
            'booking_cancelled',
            f'Admin {current_user.username} cancelled booking {booking.reference_number}',
            request,
            user_id=current_user.id,
            context={'booking_id': booking.id, 'customer_name': booking.customer_name}
        )
        
        flash(f'Booking {booking.reference_number} has been cancelled', 'success')
        return redirect(url_for('bookings.view', id=id))
    
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while cancelling the booking', 'danger')
        return redirect(url_for('bookings.view', id=id))

@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete booking with validation and audit logging"""
    try:
        if id <= 0:
            flash('Invalid booking ID', 'danger')
            return redirect(url_for('bookings.index'))
        
        booking = Booking.query.get(id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        # Store booking info for logging
        booking_info = {
            'id': booking.id,
            'reference_number': booking.reference_number,
            'customer_name': booking.customer_name,
            'amount': float(booking.total_amount) if booking.total_amount else 0
        }
        
        # Delete related booking seats first (cascade should handle this)
        db.session.delete(booking)
        db.session.commit()
        
        ErrorLogger.log_security_event(
            'booking_deleted',
            f'Admin {current_user.username} deleted booking {booking_info["reference_number"]}',
            request,
            user_id=current_user.id,
            context=booking_info
        )
        
        flash('Booking deleted successfully', 'success')
        return redirect(url_for('bookings.index'))
    
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while deleting the booking', 'danger')
        return redirect(url_for('bookings.index'))

def generate_ticket_pdf(booking_data):
    """Generate PDF ticket for booking"""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Build story
    story = []
    
    # Add title
    story.append(Paragraph("CINEMA TICKET", title_style))
    story.append(Spacer(1, 12))
    
    # Add booking details
    booking_details = [
        ['Booking Reference:', booking_data['reference_number']],
        ['Customer Name:', booking_data['customer_name']],
        ['Movie:', booking_data['movie_title']],
        ['Screen:', booking_data['screen_name']],
        ['Date:', booking_data['show_date']],
        ['Time:', booking_data['show_time']],
        ['Seats:', booking_data['seats']],
        ['Total Amount:', f"₹{booking_data['total_amount']:.2f}"]
    ]
    
    # Create table for booking details
    details_table = Table(booking_details, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    story.append(details_table)
    
    # Build PDF
    doc.build(story)
    
    # Get PDF data
    pdf_data = buffer.getvalue()
    buffer.close()
    
    return pdf_data

@bp.route('/api/search/autocomplete')
@login_required
def api_search_autocomplete():
    """API endpoint for booking search autocomplete"""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')
        
        if not query or len(query) < 2:
            return jsonify({'suggestions': []})
        
        # Use BookingSearch for autocomplete
        booking_search = BookingSearch()
        suggestions = booking_search.get_autocomplete_suggestions(query, search_type)
        
        return jsonify({'suggestions': suggestions})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        return jsonify({'suggestions': []})

@bp.route('/api/saved_searches', methods=['GET', 'POST'])
@login_required
def api_saved_searches():
    """API endpoint for managing saved searches"""
    try:
        if request.method == 'GET':
            # Get saved searches for current user
            saved_searches = SavedSearch.get_user_saved_searches(current_user.id, 'bookings')
            return jsonify({'saved_searches': [s.to_dict() for s in saved_searches]})
        
        else:  # POST
            # Save a new search
            data = request.get_json()
            if not data or not data.get('name') or not data.get('parameters'):
                return jsonify({'error': 'Name and parameters are required'}), 400
            
            saved_search = SavedSearch(
                user_id=current_user.id,
                name=data['name'],
                module='bookings',
                parameters=data['parameters']
            )
            
            db.session.add(saved_search)
            db.session.commit()
            
            return jsonify({'success': True, 'id': saved_search.id})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        if request.method == 'GET':
            return jsonify({'saved_searches': []})
        else:
            return jsonify({'error': 'Failed to save search'}), 500

@bp.route('/api/saved_searches/<int:search_id>', methods=['DELETE'])
@login_required
def api_delete_saved_search(search_id):
    """API endpoint for deleting a saved search"""
    try:
        saved_search = SavedSearch.query.filter_by(
            id=search_id,
            user_id=current_user.id
        ).first()
        
        if not saved_search:
            return jsonify({'error': 'Saved search not found'}), 404
        
        db.session.delete(saved_search)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        return jsonify({'error': 'Failed to delete saved search'}), 500

@bp.route('/search_analytics')
@login_required
@admin_required
def search_analytics():
    """Show search analytics for bookings"""
    try:
        analytics = SearchAnalytics()
        
        # Get popular search terms
        popular_terms = analytics.get_popular_searches('bookings', limit=20)
        
        # Get recent search history
        recent_searches = analytics.get_recent_searches('bookings', limit=50)
        
        # Get search performance metrics
        performance_metrics = analytics.get_search_performance('bookings')
        
        return render_template('bookings/search_analytics.html',
                             title='Booking Search Analytics',
                             popular_terms=popular_terms,
                             recent_searches=recent_searches,
                             performance_metrics=performance_metrics)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        flash('An error occurred while loading search analytics', 'danger')
        return redirect(url_for('bookings.index'))