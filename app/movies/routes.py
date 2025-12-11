"""
Movies Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.movies import bp
from app.auth.decorators import admin_required
from app.movies.models import Movie
from app.movies.forms import MovieForm
from app.database import db
from sqlalchemy import or_


@bp.route('/')
@login_required
def index():
    """Movies listing page with search and filtering"""
    # Get query parameters for search and filtering
    search_query = request.args.get('search', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    language_filter = request.args.get('language', '', type=str)
    
    # Build the base query
    query = Movie.query
    
    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Movie.name.ilike(f'%{search_query}%'),
                Movie.description.ilike(f'%{search_query}%'),
                Movie.genre.ilike(f'%{search_query}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Movie.status == status_filter)
    
    # Apply language filter
    if language_filter:
        query = query.filter(Movie.language == language_filter)
    
    # Order by name and execute query
    movies = query.order_by(Movie.name).all()
    
    # Get unique languages for filter dropdown
    languages = db.session.query(Movie.language).distinct().all()
    languages = [lang[0] for lang in languages if lang[0]]
    
    return render_template('movies/index.html',
                          title='Movies',
                          movies=movies,
                          languages=languages,
                          search_query=search_query,
                          status_filter=status_filter,
                          language_filter=language_filter)


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