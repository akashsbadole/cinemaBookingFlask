"""
Movies Routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.movies import bp
from app.auth.decorators import admin_required

@bp.route('/')
@login_required
def index():
    """Movies listing page"""
    return render_template('movies/index.html', title='Movies')

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """Add new movie"""
    return render_template('movies/add.html', title='Add Movie')

@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    """Edit movie"""
    return render_template('movies/edit.html', title='Edit Movie')

@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete movie"""
    return redirect(url_for('movies.index'))