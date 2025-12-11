"""
Screens Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.screens import bp
from app.auth.decorators import admin_required
from app.screens.forms import ScreenForm, SeatForm, BulkSeatForm, SeatLayoutForm
from app.screens.models import Screen, Seat
from app.database import db

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
        from app.bookings.models import BookingSeat
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
    from app.bookings.models import BookingSeat
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