"""
Shows Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.shows import bp
from app.auth.decorators import admin_required
from app.shows.forms import ShowForm, ShowSearchForm, AdvancedShowSearchForm
from app.shows.models import Show
from app.movies.models import Movie
from app.screens.models import Screen
from app.database import db
# Import locally to avoid circular imports
# from app.search import ShowSearch, SearchAnalytics, get_search_params_from_request
from datetime import datetime, time, timedelta
import json


@bp.route('/')
@login_required
def index():
    """Shows listing page with advanced search and filtering"""
    from app.search import ShowSearch, SearchAnalytics, get_search_params_from_request
    
    # Get search parameters from request
    params = get_search_params_from_request()
    
    # Create advanced show search
    show_search = ShowSearch()
    
    # Apply search filters
    show_search.search_shows(
        search_term=params.get('search_term'),
        movie_id=params.get('movie_id'),
        screen_id=params.get('screen_id'),
        show_date_from=params.get('date_from'),
        show_date_to=params.get('date_to'),
        show_time_from=params.get('time_from'),
        show_time_to=params.get('time_to'),
        show_type=params.get('show_type'),
        status=params.get('status'),
        min_price=params.get('min_price'),
        max_price=params.get('max_price'),
        sort_by=params.get('sort_by', 'show_date'),
        sort_order=params.get('sort_order', 'asc')
    )
    
    # Set pagination
    show_search.set_pagination(params.get('page', 1), params.get('per_page', 25))
    
    # Execute search
    search_results = show_search.execute()
    shows = search_results['results']
    
    # Track search analytics
    if params.get('search_term') or any(params.get(key) for key in ['movie_id', 'screen_id', 'show_type', 'status']):
        SearchAnalytics.track_search(
            user_id=current_user.id,
            module='shows',
            search_term=params.get('search_term'),
            search_params=json.dumps(params),
            result_count=search_results['total']
        )
    
    # Get filter options
    movies = Movie.query.filter_by(status='active').order_by(Movie.name).all()
    screens = Screen.query.order_by(Screen.name).all()
    
    # Create search form
    form = ShowSearchForm()
    
    # Pre-populate form with current search parameters
    if params.get('search_term'):
        form.search.data = params.get('search_term')
    if params.get('movie_id'):
        form.movie_id.data = params.get('movie_id')
    if params.get('screen_id'):
        form.screen_id.data = params.get('screen_id')
    if params.get('show_type'):
        form.show_type.data = params.get('show_type')
    if params.get('status'):
        form.status.data = params.get('status')
    if params.get('date_from'):
        form.date_from.data = params.get('date_from')
    if params.get('date_to'):
        form.date_to.data = params.get('date_to')
    if params.get('time_from'):
        form.time_from.data = params.get('time_from')
    if params.get('time_to'):
        form.time_to.data = params.get('time_to')
    if params.get('min_price'):
        form.min_price.data = params.get('min_price')
    if params.get('max_price'):
        form.max_price.data = params.get('max_price')
    if params.get('sort_by'):
        form.sort_by.data = params.get('sort_by')
    if params.get('sort_order'):
        form.sort_order.data = params.get('sort_order')
    if params.get('per_page'):
        form.per_page.data = params.get('per_page')
    
    return render_template('shows/index.html',
                          title='Shows',
                          shows=shows,
                          movies=movies,
                          screens=screens,
                          form=form,
                          search_params=params,
                          pagination=search_results)


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


@bp.route('/api/autocomplete')
@login_required
def api_autocomplete():
    """API endpoint for show autocomplete suggestions"""
    from app.search import ShowSearch
    
    search_term = request.args.get('q', '', type=str)
    
    if not search_term or len(search_term) < 2:
        return jsonify([])
    
    # Use advanced search for autocomplete
    show_search = ShowSearch()
    show_search.search_shows(search_term=search_term)
    show_search.set_pagination(1, 10)
    
    search_results = show_search.execute()
    
    # Format results for autocomplete
    suggestions = []
    for show in search_results['results']:
        suggestions.append({
            'id': show.id,
            'movie_name': show.movie.name if show.movie else 'Unknown',
            'screen_name': show.screen.name if show.screen else 'Unknown',
            'date': show.show_date.strftime('%Y-%m-%d') if show.show_date else None,
            'time': show.show_time.strftime('%H:%M') if show.show_time else None,
            'show_type': show.show_type
        })
    
    return jsonify(suggestions)


@bp.route('/api/saved-searches')
@login_required
def api_saved_searches():
    """API endpoint to get saved searches"""
    from app.search import SearchAnalytics
    
    saved_searches = SearchAnalytics.get_saved_searches(current_user.id, 'shows')
    return jsonify([{
        'id': search.id,
        'name': search.name,
        'params': json.loads(search.search_params),
        'is_default': search.is_default
    } for search in saved_searches])


@bp.route('/api/save-search', methods=['POST'])
@login_required
def api_save_search():
    """API endpoint to save a search"""
    from app.search import SearchAnalytics
    
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('search_params'):
        return jsonify({'error': 'Name and search parameters are required'}), 400
    
    try:
        saved_search = SearchAnalytics.save_search(
            user_id=current_user.id,
            name=data['name'],
            module='shows',
            search_params=json.dumps(data['search_params']),
            is_default=data.get('is_default', False)
        )
        
        return jsonify({
            'success': True,
            'id': saved_search.id,
            'name': saved_search.name
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/advanced-search')
@login_required
def advanced_search():
    """Advanced search page for shows"""
    from app.search import SearchAnalytics
    
    form = AdvancedShowSearchForm()
    
    # Get saved searches
    saved_searches = SearchAnalytics.get_saved_searches(current_user.id, 'shows')
    
    return render_template('shows/advanced_search.html',
                          title='Advanced Show Search',
                          form=form,
                          saved_searches=saved_searches)


@bp.route('/search-analytics')
@login_required
@admin_required
def search_analytics():
    """Show search analytics for shows"""
    from app.search import SearchAnalytics, SearchHistory
    
    # Get popular search terms
    popular_terms = SearchAnalytics.get_popular_search_terms(days=30)
    
    # Get search performance metrics
    performance_metrics = SearchAnalytics.get_search_performance_by_module(days=30)
    
    # Get recent search history
    recent_searches = SearchHistory.query.filter_by(module='shows')\
        .order_by(SearchHistory.created_at.desc())\
        .limit(20).all()
    
    return render_template('shows/search_analytics.html',
                          title='Show Search Analytics',
                          popular_terms=popular_terms,
                          performance_metrics=performance_metrics,
                          recent_searches=recent_searches)