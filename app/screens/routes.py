"""
Screens Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.screens import bp
from app.auth.decorators import admin_required
from app.screens.forms import (
    ScreenForm, SeatForm, BulkSeatForm, SeatLayoutForm,
    BulkUpdateSeatTypesForm, BulkUpdatePricesForm, 
    SeatAvailabilityForm, SeatUtilizationForm
)
from app.screens.models import Screen, Seat, SeatLock
from app.screens.utils import (
    check_seat_availability, get_seat_layout_with_availability,
    lock_seats_for_booking, release_seat_locks, cleanup_expired_locks,
    get_seat_utilization_report, update_seat_prices, bulk_update_seat_types,
    get_seat_pricing_matrix, apply_dynamic_pricing, get_seat_availability_summary
)
from app.database import db
from datetime import datetime, timedelta

@bp.route('/')
@login_required
def index():
    """Screens listing page"""
    screens = Screen.query.all()
    return render_template('screens/index.html', title='Screens', screens=screens)

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """Add new screen"""
    form = ScreenForm()
    
    if form.validate_on_submit():
        screen = Screen(
            name=form.name.data,
            total_rows=form.total_rows.data,
            total_columns=form.total_columns.data
        )
        db.session.add(screen)
        db.session.commit()
        
        # Check if auto-generate seats is requested
        auto_generate = request.form.get('auto_generate_seats') == 'on'
        if auto_generate:
            pattern = request.form.get('seat_pattern', 'regular')
            normal_price = float(request.form.get('normal_price', 100))
            premium_price = float(request.form.get('premium_price', 150))
            vip_price = float(request.form.get('vip_price', 250))
            
            screen.generate_seats(
                pattern=pattern,
                normal_price=normal_price,
                premium_price=premium_price,
                vip_price=vip_price,
                clear_existing=False
            )
            
            flash(f'Screen "{screen.name}" has been created with seats successfully!', 'success')
        else:
            flash(f'Screen "{screen.name}" has been created successfully!', 'success')
        
        return redirect(url_for('screens.index'))
    
    return render_template('screens/add.html', title='Add Screen', form=form)

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Edit screen"""
    screen = Screen.query.get_or_404(id)
    form = ScreenForm(obj=screen)
    
    if form.validate_on_submit():
        screen.name = form.name.data
        screen.total_rows = form.total_rows.data
        screen.total_columns = form.total_columns.data
        db.session.commit()
        flash(f'Screen "{screen.name}" has been updated successfully!', 'success')
        return redirect(url_for('screens.index'))
    
    return render_template('screens/edit.html', title='Edit Screen', form=form, screen=screen)

@bp.route('/<int:screen_id>/seats')
@login_required
def manage_seats(screen_id):
    """Manage seats for a screen"""
    screen = Screen.query.get_or_404(screen_id)
    seats_grid = screen.get_seats_grid()
    seat_counts = screen.get_seat_count_by_type()
    
    return render_template('screens/manage_seats.html', 
                          title=f'Manage Seats - {screen.name}',
                          screen=screen, 
                          seats_grid=seats_grid,
                          seat_counts=seat_counts)

@bp.route('/<int:screen_id>/seats/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_seat(screen_id):
    """Add a single seat to a screen"""
    screen = Screen.query.get_or_404(screen_id)
    form = SeatForm()
    
    # Set screen ID
    form.screen_id.data = screen_id
    
    # Generate row and column options
    form.row.choices = [(chr(65 + i), chr(65 + i)) for i in range(screen.total_rows)]
    form.column.choices = [(i, str(i)) for i in range(1, screen.total_columns + 1)]
    
    if form.validate_on_submit():
        # Check if seat already exists
        existing_seat = Seat.query.filter_by(
            screen_id=screen_id,
            row=form.row.data,
            column=form.column.data
        ).first()
        
        if existing_seat:
            flash(f'Seat {form.row.data}{form.column.data} already exists!', 'danger')
            return redirect(url_for('screens.add_seat', screen_id=screen_id))
        
        seat = Seat(
            screen_id=screen_id,
            row=form.row.data,
            column=form.column.data,
            type=form.type.data,
            price=form.price.data
        )
        
        db.session.add(seat)
        db.session.commit()
        
        flash(f'Seat {form.row.data}{form.column.data} has been added successfully!', 'success')
        return redirect(url_for('screens.manage_seats', screen_id=screen_id))
    
    return render_template('screens/add_seat.html', 
                          title=f'Add Seat - {screen.name}',
                          form=form, 
                          screen=screen)

@bp.route('/seats/<int:seat_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_seat(seat_id):
    """Edit a seat"""
    seat = Seat.query.get_or_404(seat_id)
    form = SeatForm(obj=seat)
    
    # Set screen ID
    form.screen_id.data = seat.screen_id
    
    # Generate row and column options
    screen = seat.screen
    form.row.choices = [(chr(65 + i), chr(65 + i)) for i in range(screen.total_rows)]
    form.column.choices = [(i, str(i)) for i in range(1, screen.total_columns + 1)]
    
    if form.validate_on_submit():
        # Check if seat location conflicts with another seat
        conflict_seat = Seat.query.filter(
            Seat.screen_id == seat.screen_id,
            Seat.row == form.row.data,
            Seat.column == form.column.data,
            Seat.id != seat_id
        ).first()
        
        if conflict_seat:
            flash(f'Seat {form.row.data}{form.column.data} already exists!', 'danger')
            return redirect(url_for('screens.edit_seat', seat_id=seat_id))
        
        # Check if seat has bookings
        from app.bookings.models import BookingSeat, Booking
        active_bookings = BookingSeat.query.filter_by(seat_id=seat_id).join('booking').filter(
            Booking.status.in_(['confirmed', 'pending'])
        ).count()
        
        if active_bookings > 0:
            flash(f'Cannot edit seat {seat.row}{seat.column} - it has active bookings!', 'danger')
            return redirect(url_for('screens.manage_seats', screen_id=seat.screen_id))
        
        seat.row = form.row.data
        seat.column = form.column.data
        seat.type = form.type.data
        seat.price = form.price.data
        
        db.session.commit()
        
        flash(f'Seat {seat.row}{seat.column} has been updated successfully!', 'success')
        return redirect(url_for('screens.manage_seats', screen_id=seat.screen_id))
    
    return render_template('screens/edit_seat.html', 
                          title=f'Edit Seat {seat.row}{seat.column}',
                          form=form, 
                          seat=seat,
                          screen=seat.screen)

@bp.route('/seats/<int:seat_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_seat(seat_id):
    """Delete a seat"""
    seat = Seat.query.get_or_404(seat_id)
    
    # Check if seat has bookings
    from app.bookings.models import BookingSeat, Booking
    active_bookings = BookingSeat.query.filter_by(seat_id=seat_id).join('booking').filter(
        Booking.status.in_(['confirmed', 'pending'])
    ).count()
    
    if active_bookings > 0:
        flash(f'Cannot delete seat {seat.row}{seat.column} - it has active bookings!', 'danger')
        return redirect(url_for('screens.manage_seats', screen_id=seat.screen_id))
    
    seat_name = f"{seat.row}{seat.column}"
    screen_id = seat.screen_id
    
    db.session.delete(seat)
    db.session.commit()
    
    flash(f'Seat {seat_name} has been deleted successfully!', 'success')
    return redirect(url_for('screens.manage_seats', screen_id=screen_id))

@bp.route('/<int:screen_id>/seats/generate', methods=['GET', 'POST'])
@login_required
@admin_required
def generate_seats(screen_id):
    """Generate seats for a screen"""
    screen = Screen.query.get_or_404(screen_id)
    form = BulkSeatForm()
    
    # Set screen ID
    form.screen_id.data = screen_id
    
    if form.validate_on_submit():
        try:
            screen.generate_seats(
                pattern=form.pattern.data,
                normal_price=float(form.normal_price.data),
                premium_price=float(form.premium_price.data),
                vip_price=float(form.vip_price.data),
                clear_existing=form.clear_existing.data
            )
            
            flash(f'Seats have been generated for {screen.name}!', 'success')
            return redirect(url_for('screens.manage_seats', screen_id=screen_id))
        except Exception as e:
            flash(f'Error generating seats: {str(e)}', 'danger')
    
    return render_template('screens/generate_seats.html', 
                          title=f'Generate Seats - {screen.name}',
                          form=form, 
                          screen=screen)

@bp.route('/<int:screen_id>/seats/layout', methods=['GET', 'POST'])
@login_required
@admin_required
def custom_layout(screen_id):
    """Apply custom seat layout"""
    screen = Screen.query.get_or_404(screen_id)
    form = SeatLayoutForm()
    
    # Set screen ID
    form.screen_id.data = screen_id
    
    # Generate example layout
    example_layout = []
    for i in range(min(3, screen.total_rows)):
        row_letter = chr(65 + i)
        pattern = ''.join(['N'] * screen.total_columns)
        example_layout.append(f"{row_letter}:{pattern}")
    
    example_text = '\n'.join(example_layout)
    
    if form.validate_on_submit():
        try:
            screen.apply_custom_layout(
                layout_definition=form.layout_definition.data,
                normal_price=100.00,
                premium_price=150.00,
                vip_price=250.00
            )
            
            flash(f'Custom layout has been applied to {screen.name}!', 'success')
            return redirect(url_for('screens.manage_seats', screen_id=screen_id))
        except Exception as e:
            flash(f'Error applying layout: {str(e)}', 'danger')
    
    return render_template('screens/custom_layout.html', 
                          title=f'Custom Layout - {screen.name}',
                          form=form, 
                          screen=screen,
                          example_text=example_text)

@bp.route('/<int:screen_id>/seats/bulk-update-types', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_update_seat_types(screen_id):
    """Bulk update seat types"""
    screen = Screen.query.get_or_404(screen_id)
    form = BulkUpdateSeatTypesForm()
    
    # Set screen ID
    form.screen_id.data = screen_id
    
    if form.validate_on_submit():
        try:
            # Parse seat updates
            updates = {}
            for line in form.seat_updates.data.strip().split('\n'):
                if ':' in line:
                    seat_id, seat_type = line.strip().split(':', 1)
                    updates[seat_id.strip()] = seat_type.strip().lower()
            
            result = bulk_update_seat_types(screen_id, updates)
            
            if result['success']:
                flash(f"Updated {result['updated_count']} seats successfully!", 'success')
                
                if result['errors']:
                    flash(f"Failed to update {len(result['errors'])} seats.", 'warning')
                    for error in result['errors']:
                        flash(f"Seat {error['seat']}: {error['reason']}", 'warning')
            else:
                flash(f"Error updating seats: {result.get('message', 'Unknown error')}", 'danger')
            
            return redirect(url_for('screens.manage_seats', screen_id=screen_id))
        except Exception as e:
            flash(f'Error updating seat types: {str(e)}', 'danger')
    
    return render_template('screens/bulk_update_types.html', 
                          title=f'Bulk Update Seat Types - {screen.name}',
                          form=form, 
                          screen=screen)

@bp.route('/<int:screen_id>/seats/bulk-update-prices', methods=['GET', 'POST'])
@login_required
@admin_required
def bulk_update_prices(screen_id):
    """Bulk update seat prices"""
    screen = Screen.query.get_or_404(screen_id)
    form = BulkUpdatePricesForm()
    
    # Set screen ID and current prices
    form.screen_id.data = screen_id
    
    # Get current prices by type
    seat_counts = screen.get_seat_count_by_type()
    current_prices = {}
    
    for seat_type in ['normal', 'premium', 'vip']:
        seats = Seat.query.filter_by(screen_id=screen_id, type=seat_type).first()
        if seats:
            current_prices[seat_type] = float(seats.price)
        else:
            current_prices[seat_type] = 100.00 if seat_type == 'normal' else (150.00 if seat_type == 'premium' else 250.00)
    
    if request.method == 'GET':
        form.normal_price.data = current_prices['normal']
        form.premium_price.data = current_prices['premium']
        form.vip_price.data = current_prices['vip']
    
    if form.validate_on_submit():
        try:
            price_updates = {
                'normal': float(form.normal_price.data),
                'premium': float(form.premium_price.data),
                'vip': float(form.vip_price.data)
            }
            
            result = update_seat_prices(screen_id, price_updates)
            
            if result['success']:
                flash(result['message'], 'success')
            else:
                flash(result['message'], 'danger')
            
            return redirect(url_for('screens.manage_seats', screen_id=screen_id))
        except Exception as e:
            flash(f'Error updating prices: {str(e)}', 'danger')
    
    return render_template('screens/bulk_update_prices.html', 
                          title=f'Bulk Update Prices - {screen.name}',
                          form=form, 
                          screen=screen,
                          seat_counts=seat_counts,
                          current_prices=current_prices)

@bp.route('/seat-availability', methods=['GET', 'POST'])
@login_required
def seat_availability():
    """Check seat availability for shows"""
    form = SeatAvailabilityForm()
    
    # Populate screen choices
    screens = Screen.query.all()
    form.screen_id.choices = [(s.id, s.name) for s in screens]
    
    # Initialize show choices (will be populated by JavaScript)
    form.show_id.choices = [(0, 'Select a screen first')]
    
    if form.validate_on_submit() and form.show_id.data != 0:
        try:
            screen_id = form.screen_id.data
            show_id = form.show_id.data
            
            # Get seat layout with availability
            layout_data = get_seat_layout_with_availability(screen_id, show_id)
            
            if layout_data:
                return render_template('screens/seat_availability.html', 
                                      title='Seat Availability',
                                      form=form,
                                      layout_data=layout_data)
            else:
                flash('No seat layout found for this screen.', 'danger')
                return redirect(url_for('screens.seat_availability'))
        except Exception as e:
            flash(f'Error checking seat availability: {str(e)}', 'danger')
    
    return render_template('screens/seat_availability.html', 
                          title='Seat Availability',
                          form=form,
                          layout_data=None)

@bp.route('/seat-utilization', methods=['GET', 'POST'])
@login_required
def seat_utilization():
    """Generate seat utilization reports"""
    form = SeatUtilizationForm()
    
    # Populate screen choices
    screens = Screen.query.all()
    form.screen_id.choices = [(s.id, s.name) for s in screens]
    
    # Set default date range (last 30 days)
    if request.method == 'GET':
        form.start_date.data = datetime.now() - timedelta(days=30)
        form.end_date.data = datetime.now()
    
    if form.validate_on_submit():
        try:
            screen_id = form.screen_id.data
            start_date = form.start_date.data
            end_date = form.end_date.data
            
            # Get utilization report
            report_data = get_seat_utilization_report(screen_id, start_date, end_date)
            
            if report_data:
                return render_template('screens/seat_utilization.html', 
                                      title='Seat Utilization Report',
                                      form=form,
                                      report_data=report_data)
            else:
                flash('No utilization data found for this screen.', 'danger')
                return redirect(url_for('screens.seat_utilization'))
        except Exception as e:
            flash(f'Error generating utilization report: {str(e)}', 'danger')
    
    return render_template('screens/seat_utilization.html', 
                          title='Seat Utilization Report',
                          form=form,
                          report_data=None)

@bp.route('/<int:screen_id>/seats/api', methods=['GET'])
@login_required
def get_seats_api(screen_id):
    """API endpoint to get seat data for a screen"""
    screen = Screen.query.get_or_404(screen_id)
    seats_grid = screen.get_seats_grid()
    
    seats_data = []
    for row_letter in sorted(seats_grid.keys()):
        for col in sorted(seats_grid[row_letter].keys()):
            seat = seats_grid[row_letter][col]
            seats_data.append({
                'id': seat.id,
                'row': seat.row,
                'column': seat.column,
                'type': seat.type,
                'price': float(seat.price),
                'name': f"{seat.row}{seat.column}"
            })
    
    return jsonify({
        'screen': {
            'id': screen.id,
            'name': screen.name,
            'total_rows': screen.total_rows,
            'total_columns': screen.total_columns
        },
        'seats': seats_data
    })

@bp.route('/<int:screen_id>/shows/<int:show_id>/seats/api', methods=['GET'])
@login_required
def get_seats_with_availability_api(screen_id, show_id):
    """API endpoint to get seat data with availability for a specific show"""
    layout_data = get_seat_layout_with_availability(screen_id, show_id)
    
    if not layout_data:
        return jsonify({'error': 'Screen or show not found'}), 404
    
    return jsonify(layout_data)

@bp.route('/cleanup-expired-locks', methods=['POST'])
@login_required
@admin_required
def cleanup_expired_locks_route():
    """Clean up expired seat locks"""
    try:
        count = cleanup_expired_locks()
        flash(f'Cleaned up {count} expired seat locks.', 'success')
    except Exception as e:
        flash(f'Error cleaning up expired locks: {str(e)}', 'danger')
    
    return redirect(url_for('screens.index'))

@bp.route('/api/shows/<int:screen_id>')
@login_required
def get_shows_for_screen(screen_id):
    """API endpoint to get shows for a specific screen"""
    from app.shows.models import Show
    
    shows = Show.query.filter_by(
        screen_id=screen_id,
        status='scheduled'
    ).filter(
        Show.show_date >= datetime.now().date()
    ).order_by(Show.show_date, Show.show_time).all()
    
    shows_data = [(0, 'Select a show')]
    shows_data.extend([(s.id, f"{s.show_date.strftime('%Y-%m-%d')} {s.show_time.strftime('%H:%M')} - {s.movie.name}") for s in shows])
    
    return jsonify(shows_data)

@bp.route('/<int:screen_id>/pricing-matrix', methods=['GET'])
@login_required
def pricing_matrix(screen_id):
    """View pricing matrix for a screen"""
    from app.screens.utils import get_seat_pricing_matrix
    
    pricing_data = get_seat_pricing_matrix(screen_id)
    
    if not pricing_data:
        flash('Screen not found', 'danger')
        return redirect(url_for('screens.index'))
    
    return render_template('screens/pricing_matrix.html',
                          title=f'Pricing Matrix - {pricing_data["screen"]["name"]}',
                          pricing_data=pricing_data)

@bp.route('/<int:screen_id>/dynamic-pricing', methods=['GET', 'POST'])
@login_required
@admin_required
def dynamic_pricing(screen_id):
    """Apply dynamic pricing rules"""
    from app.screens.utils import apply_dynamic_pricing
    
    if request.method == 'GET':
        screen = Screen.query.get_or_404(screen_id)
        return render_template('screens/dynamic_pricing.html',
                              title=f'Dynamic Pricing - {screen.name}',
                              screen=screen)
    
    elif request.method == 'POST':
        show_id = request.form.get('show_id', type=int)
        weekend_surcharge = float(request.form.get('weekend_surcharge', 1.2))
        matinee_discount = float(request.form.get('matinee_discount', 0.9))
        evening_surcharge = float(request.form.get('evening_surcharge', 1.1))
        holiday_surcharge = float(request.form.get('holiday_surcharge', 1.5))
        
        pricing_rules = {
            'weekend_surcharge': weekend_surcharge,
            'matinee_discount': matinee_discount,
            'evening_surcharge': evening_surcharge,
            'holiday_surcharge': holiday_surcharge
        }
        
        result = apply_dynamic_pricing(screen_id, show_id, pricing_rules)
        
        if result['success']:
            flash(f'Dynamic pricing has been applied successfully!', 'success')
        else:
            flash(f'Error applying dynamic pricing: {result.get("message", "Unknown error")}', 'danger')
        
        return redirect(url_for('screens.manage_seats', screen_id=screen_id))

@bp.route('/<int:screen_id>/shows/<int:show_id>/availability-summary', methods=['GET'])
@login_required
def seat_availability_summary(screen_id, show_id):
    """Get detailed seat availability summary for a show"""
    from app.screens.utils import get_seat_availability_summary
    
    summary_data = get_seat_availability_summary(screen_id, show_id)
    
    if not summary_data:
        flash('Screen or show not found', 'danger')
        return redirect(url_for('screens.index'))
    
    return render_template('screens/availability_summary.html',
                          title=f'Seat Availability - {summary_data["screen"]["name"]}',
                          summary_data=summary_data)


@bp.route('/<int:screen_id>/shows/<int:show_id>/lock-seats', methods=['POST'])
@login_required
def lock_seats(screen_id, show_id):
    """Lock seats for a show"""
    seat_ids = request.json.get('seat_ids', [])
    
    if not seat_ids:
        return jsonify({'success': False, 'message': 'No seats selected'}), 400
    
    try:
        result = lock_seats_for_booking(seat_ids, show_id, current_user.id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Successfully locked {len(result["locked_seats"])} seats',
                'locked_seats': [seat.id for seat in result['locked_seats']],
                'errors': result['errors']
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to lock seats',
                'errors': result['errors']
            }), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/<int:screen_id>/shows/<int:show_id>/release-seats', methods=['POST'])
@login_required
def release_seats(screen_id, show_id):
    """Release locked seats for a show"""
    seat_ids = request.json.get('seat_ids', [])
    
    if not seat_ids:
        return jsonify({'success': False, 'message': 'No seats selected'}), 400
    
    try:
        released_count = release_seat_locks(seat_ids, show_id, current_user.id)
        
        return jsonify({
            'success': True,
            'message': f'Successfully released {released_count} seat locks',
            'released_count': released_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/shows/<int:show_id>/locked-seats', methods=['GET'])
@login_required
def get_locked_seats(show_id):
    """Get all locked seats for a show"""
    try:
        locked_seats = SeatLock.get_locked_seats_for_show(show_id)
        
        seats_data = []
        for lock in locked_seats:
            seats_data.append({
                'id': lock.seat.id,
                'seat_number': lock.seat.seat_number,
                'row': lock.seat.row,
                'column': lock.seat.column,
                'type': lock.seat.type,
                'user_id': lock.user_id,
                'lock_time': lock.lock_time.strftime('%Y-%m-%d %H:%M:%S'),
                'expires_at': lock.expires_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({
            'success': True,
            'locked_seats': seats_data,
            'count': len(seats_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500