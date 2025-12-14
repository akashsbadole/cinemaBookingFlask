"""
Shows Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.shows import bp
from app.auth.decorators import admin_required
from app.shows.forms import ShowForm
from app.shows.models import Show
from app.movies.models import Movie
from app.screens.models import Screen
from app.database import db
from datetime import datetime, time, timedelta


@bp.route('/')
@login_required
def index():
    """Shows listing page"""
    # Get filter parameters
    movie_id = request.args.get('movie_id', type=int)
    screen_id = request.args.get('screen_id', type=int)
    date_filter = request.args.get('date')
    
    # Build query
    query = Show.query
    
    # Apply filters
    if movie_id:
        query = query.filter(Show.movie_id == movie_id)
    if screen_id:
        query = query.filter(Show.screen_id == screen_id)
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(Show.show_date == filter_date)
        except ValueError:
            pass
    
    # Get shows ordered by date and time
    shows = query.order_by(Show.show_date.desc(), Show.show_time.asc()).all()
    
    # Get filter options
    movies = Movie.query.filter_by(status='active').order_by(Movie.name).all()
    screens = Screen.query.order_by(Screen.name).all()
    
    return render_template('shows/index.html', title='Shows', shows=shows, movies=movies, screens=screens)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """Add new show"""
    form = ShowForm()
    
    if form.validate_on_submit():
        # Get movie duration to calculate end time
        movie = Movie.query.get(form.movie_id.data)
        end_time = (datetime.combine(datetime.today(), form.show_time.data) + 
                    timedelta(minutes=movie.duration)).time()
        
        # Check for scheduling conflicts
        conflict_show = Show.query.filter_by(
            screen_id=form.screen_id.data,
            show_date=form.show_date.data
        ).filter(
            # Check if new show time conflicts with existing shows
            (Show.show_time <= form.show_time.data) & (Show.end_time > form.show_time.data) |
            (Show.show_time < end_time) & (Show.end_time >= end_time) |
            (Show.show_time >= form.show_time.data) & (Show.show_time < end_time)
        ).first()
        
        if conflict_show:
            flash(f'Scheduling conflict! There is already a show in {conflict_show.screen.name} at that time.', 'danger')
            return render_template('shows/add.html', title='Add Show', form=form)
        
        # Create new show
        show = Show(
            movie_id=form.movie_id.data,
            screen_id=form.screen_id.data,
            show_date=form.show_date.data,
            show_time=form.show_time.data,
            end_time=end_time,
            base_price=form.base_price.data,
            weekend_surcharge=form.weekend_surcharge.data,
            matinee_discount=form.matinee_discount.data,
            show_type=form.show_type.data
        )
        db.session.add(show)
        db.session.commit()
        flash(f'Show for "{show.movie.name}" has been created successfully!', 'success')
        return redirect(url_for('shows.index'))
    
    return render_template('shows/add.html', title='Add Show', form=form)


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Edit show"""
    show = Show.query.get_or_404(id)
    form = ShowForm(obj=show)
    
    if form.validate_on_submit():
        # Get movie duration to calculate end time
        movie = Movie.query.get(form.movie_id.data)
        end_time = (datetime.combine(datetime.today(), form.show_time.data) + 
                    timedelta(minutes=movie.duration)).time()
        
        # Check for scheduling conflicts (exclude current show)
        conflict_show = Show.query.filter(
            Show.screen_id == form.screen_id.data,
            Show.show_date == form.show_date.data,
            Show.id != id
        ).filter(
            # Check if new show time conflicts with existing shows
            (Show.show_time <= form.show_time.data) & (Show.end_time > form.show_time.data) |
            (Show.show_time < end_time) & (Show.end_time >= end_time) |
            (Show.show_time >= form.show_time.data) & (Show.show_time < end_time)
        ).first()
        
        if conflict_show:
            flash(f'Scheduling conflict! There is already a show in {conflict_show.screen.name} at that time.', 'danger')
            return render_template('shows/edit.html', title='Edit Show', form=form, show=show)
        
        # Update show
        show.movie_id = form.movie_id.data
        show.screen_id = form.screen_id.data
        show.show_date = form.show_date.data
        show.show_time = form.show_time.data
        show.end_time = end_time
        show.base_price = form.base_price.data
        show.weekend_surcharge = form.weekend_surcharge.data
        show.matinee_discount = form.matinee_discount.data
        show.show_type = form.show_type.data
        
        db.session.commit()
        flash(f'Show for "{show.movie.name}" has been updated successfully!', 'success')
        return redirect(url_for('shows.index'))
    
    return render_template('shows/edit.html', title='Edit Show', form=form, show=show)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete show"""
    show = Show.query.get_or_404(id)
    
    # Check if show has bookings
    if show.bookings:
        flash(f'Cannot delete show "{show.movie.name}" - it has existing bookings!', 'danger')
        return redirect(url_for('shows.index'))
    
    movie_name = show.movie.name
    db.session.delete(show)
    db.session.commit()
    flash(f'Show for "{movie_name}" has been deleted successfully!', 'success')
    return redirect(url_for('shows.index'))


@bp.route('/api/check_conflicts', methods=['POST'])
@login_required
@admin_required
def check_conflicts():
    """API endpoint to check for scheduling conflicts"""
    screen_id = request.json.get('screen_id')
    show_date = request.json.get('show_date')
    show_time = request.json.get('show_time')
    movie_id = request.json.get('movie_id')
    show_id = request.json.get('show_id')  # For editing existing shows
    
    if not all([screen_id, show_date, show_time, movie_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Parse date and time
        show_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        show_time = datetime.strptime(show_time, '%H:%M').time()
        
        # Get movie duration to calculate end time
        movie = Movie.query.get(movie_id)
        end_time = (datetime.combine(datetime.today(), show_time) + 
                    timedelta(minutes=movie.duration)).time()
        
        # Build query
        query = Show.query.filter_by(screen_id=screen_id, show_date=show_date)
        
        # Exclude current show if editing
        if show_id:
            query = query.filter(Show.id != show_id)
        
        # Check for conflicts
        conflict_show = query.filter(
            (Show.show_time <= show_time) & (Show.end_time > show_time) |
            (Show.show_time < end_time) & (Show.end_time >= end_time) |
            (Show.show_time >= show_time) & (Show.show_time < end_time)
        ).first()
        
        if conflict_show:
            return jsonify({
                'conflict': True,
                'message': f'Conflicts with show "{conflict_show.movie.name}" at {conflict_show.show_time.strftime("%H:%M")} - {conflict_show.end_time.strftime("%H:%M")}'
            })
        
        return jsonify({'conflict': False})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/view/<int:id>')
@login_required
def view(id):
    """View show details"""
    show = Show.query.get_or_404(id)
    
    # Get seat availability information
    total_seats = show.get_total_seats_count()
    available_seats = len(show.get_available_seats())
    occupied_seats = total_seats - available_seats
    occupancy_percentage = show.get_occupancy_percentage()
    
    return render_template('shows/view.html', 
                        title='Show Details', 
                        show=show,
                        total_seats=total_seats,
                        available_seats=available_seats,
                        occupied_seats=occupied_seats,
                        occupancy_percentage=occupancy_percentage)

@bp.route('/<int:id>/seats')
@login_required
def show_seats(id):
    """View seat layout and availability for a show"""
    from app.screens.utils import get_seat_layout_with_availability
    
    show = Show.query.get_or_404(id)
    
    # Get seat layout with availability
    layout_data = get_seat_layout_with_availability(show.screen_id, show.id)
    
    return render_template('shows/show_seats.html',
                        title=f'Seat Layout - {show.movie.name}',
                        show=show,
                        layout_data=layout_data)


@bp.route('/<int:id>/seat-layout')
@login_required
def seat_layout(id):
    """Display seat layout with availability for a show"""
    from app.screens.utils import get_seat_layout_with_availability
    
    show = Show.query.get_or_404(id)
    
    # Get seat layout with availability
    layout_data = get_seat_layout_with_availability(show.screen_id, show.id)
    
    # Get seat statistics
    total_seats = len(layout_data.get('seats', []))
    available_seats = sum(1 for seat in layout_data.get('seats', []) if seat.get('status') == 'available')
    booked_seats = sum(1 for seat in layout_data.get('seats', []) if seat.get('status') == 'booked')
    locked_seats = sum(1 for seat in layout_data.get('seats', []) if seat.get('status') == 'locked')
    
    return render_template('shows/seat_layout.html',
                        title=f'Seat Layout - {show.movie.name}',
                        show=show,
                        layout_data=layout_data,
                        total_seats=total_seats,
                        available_seats=available_seats,
                        booked_seats=booked_seats,
                        locked_seats=locked_seats)