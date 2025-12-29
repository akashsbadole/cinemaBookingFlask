"""
Movies Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.movies import bp
from app.auth.decorators import admin_required
from app.movies.models import Movie
from app.movies.forms import MovieForm, MovieSearchForm, AdvancedMovieSearchForm
from app.database import db
from app.search import MovieSearch, SearchAnalytics, get_search_params_from_request
import json


@bp.route('/')
@login_required
def index():
    """Movies listing page with advanced search and filtering"""
    # Get search parameters from request
    params = get_search_params_from_request(None)
    
    # Create advanced movie search
    movie_search = MovieSearch()
    
    # Apply search filters
    movie_search.search_movies(
        search_term=params.get('search_term'),
        genre=params.get('genre'),
        language=params.get('language'),
        rating=params.get('rating'),
        status=params.get('status'),
        min_duration=params.get('min_duration'),
        max_duration=params.get('max_duration'),
        release_date_from=params.get('release_date_from'),
        release_date_to=params.get('release_date_to'),
        sort_by=params.get('sort_by', 'name'),
        sort_order=params.get('sort_order', 'asc')
    )
    
    # Set pagination
    movie_search.set_pagination(params.get('page', 1), params.get('per_page', 12))
    
    # Execute search
    search_results = movie_search.execute()
    movies = search_results['results']
    
    # Track search analytics
    if params.get('search_term') or any(params.get(key) for key in ['genre', 'language', 'rating', 'status']):
        SearchAnalytics.track_search(
            user_id=current_user.id,
            module='movies',
            search_term=params.get('search_term'),
            search_params=json.dumps(params),
            result_count=search_results['total']
        )
    
    # Get unique languages for filter dropdown
    languages = db.session.query(Movie.language).distinct().all()
    languages = [lang[0] for lang in languages if lang[0]]
    
    # Create search form
    form = MovieSearchForm()
    
    # Pre-populate form with current search parameters
    if params.get('search_term'):
        form.search.data = params.get('search_term')
    if params.get('genre'):
        form.genre.data = params.get('genre')
    if params.get('language'):
        form.language.data = params.get('language')
    if params.get('rating'):
        form.rating.data = params.get('rating')
    if params.get('status'):
        form.status.data = params.get('status')
    
    return render_template('movies/index.html',
                          title='Movies',
                          movies=movies,
                          languages=languages,
                          form=form,
                          search_params=params,
                          pagination=search_results)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """Add new movie"""
    form = MovieForm()
    
    if form.validate_on_submit():
        # Create new movie
        movie = Movie(
            name=form.name.data,
            description=form.description.data,
            duration=form.duration.data,
            genre=form.genre.data,
            release_date=form.release_date.data,
            poster_url=form.poster_url.data,
            rating=form.rating.data,
            language=form.language.data,
            status=form.status.data
        )
        
        # Add to database
        db.session.add(movie)
        db.session.commit()
        
        flash(f'Movie "{movie.name}" has been added successfully!', 'success')
        return redirect(url_for('movies.index'))
    
    # If form validation fails, re-render the template with errors
    return render_template('movies/add.html', title='Add Movie', form=form)


@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Edit movie"""
    movie = Movie.query.get_or_404(id)
    form = MovieForm(obj=movie)
    
    # Set the _obj attribute to help with validation (for title uniqueness check)
    form._obj = movie
    
    if form.validate_on_submit():
        # Update movie properties
        movie.name = form.name.data
        movie.description = form.description.data
        movie.duration = form.duration.data
        movie.genre = form.genre.data
        movie.release_date = form.release_date.data
        movie.poster_url = form.poster_url.data
        movie.rating = form.rating.data
        movie.language = form.language.data
        movie.status = form.status.data
        
        # Update the database
        db.session.commit()
        
        flash(f'Movie "{movie.name}" has been updated successfully!', 'success')
        return redirect(url_for('movies.index'))
    
    # Pre-populate the form with current movie data for GET requests
    if request.method == 'GET':
        form.name.data = movie.name
        form.description.data = movie.description
        form.duration.data = movie.duration
        form.genre.data = movie.genre
        form.release_date.data = movie.release_date
        form.poster_url.data = movie.poster_url
        form.rating.data = movie.rating
        form.language.data = movie.language
        form.status.data = movie.status
    
    return render_template('movies/edit.html', title='Edit Movie', form=form, movie=movie)


@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete movie"""
    movie = Movie.query.get_or_404(id)
    
    # Check if movie has associated shows
    if movie.shows:
        flash(f'Cannot delete movie "{movie.name}" because it has associated shows. Delete the shows first.', 'danger')
        return redirect(url_for('movies.index'))
    
    movie_name = movie.name
    db.session.delete(movie)
    db.session.commit()
    
    flash(f'Movie "{movie_name}" has been deleted successfully!', 'success')
    return redirect(url_for('movies.index'))


@bp.route('/view/<int:id>')
@login_required
def view(id):
    """View movie details"""
    movie = Movie.query.get_or_404(id)
    return render_template('movies/view.html', title=movie.name, movie=movie)


@bp.route('/api/search')
@login_required
def api_search():
    """API endpoint for movie search"""
    search_query = request.args.get('q', '', type=str)
    
    if not search_query:
        return jsonify([])
    
    movies = Movie.query.filter(
        or_(
            Movie.name.ilike(f'%{search_query}%'),
            Movie.genre.ilike(f'%{search_query}%')
        )
    ).filter_by(status='active').limit(10).all()
    
    return jsonify([movie.to_dict() for movie in movies])


@bp.route('/api/<int:id>')
@login_required
def api_get_movie(id):
    """API endpoint to get movie details"""
    movie = Movie.query.get_or_404(id)
    return jsonify(movie.to_dict())


@bp.route('/api/autocomplete')
@login_required
def api_autocomplete():
    """API endpoint for movie autocomplete suggestions"""
    search_term = request.args.get('q', '', type=str)
    
    if not search_term or len(search_term) < 2:
        return jsonify([])
    
    # Use advanced search for autocomplete
    movie_search = MovieSearch()
    movie_search.search_movies(search_term=search_term)
    movie_search.set_pagination(1, 10)
    
    search_results = movie_search.execute()
    
    # Format results for autocomplete
    suggestions = []
    for movie in search_results['results']:
        suggestions.append({
            'id': movie.id,
            'name': movie.name,
            'genre': movie.genre,
            'year': movie.release_date.year if movie.release_date else None,
            'poster_url': movie.poster_url
        })
    
    return jsonify(suggestions)


@bp.route('/api/saved-searches')
@login_required
def api_saved_searches():
    """API endpoint to get saved searches"""
    saved_searches = SearchAnalytics.get_saved_searches(current_user.id, 'movies')
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
    data = request.get_json()
    
    if not data or not data.get('name') or not data.get('search_params'):
        return jsonify({'error': 'Name and search parameters are required'}), 400
    
    try:
        saved_search = SearchAnalytics.save_search(
            user_id=current_user.id,
            name=data['name'],
            module='movies',
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
    """Advanced search page for movies"""
    form = AdvancedMovieSearchForm()
    
    # Get saved searches
    saved_searches = SearchAnalytics.get_saved_searches(current_user.id, 'movies')
    
    return render_template('movies/advanced_search.html',
                          title='Advanced Movie Search',
                          form=form,
                          saved_searches=saved_searches)


@bp.route('/search-analytics')
@login_required
@admin_required
def search_analytics():
    """Show search analytics for movies"""
    # Get popular search terms
    popular_terms = SearchAnalytics.get_popular_search_terms(days=30)
    
    # Get search performance metrics
    performance_metrics = SearchAnalytics.get_search_performance_by_module(days=30)
    
    # Get recent search history
    recent_searches = SearchHistory.query.filter_by(module='movies')\
        .order_by(SearchHistory.created_at.desc())\
        .limit(20).all()
    
    return render_template('movies/search_analytics.html',
                          title='Movie Search Analytics',
                          popular_terms=popular_terms,
                          performance_metrics=performance_metrics,
                          recent_searches=recent_searches)