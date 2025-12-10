"""
Screens Routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.screens import bp
from app.auth.decorators import admin_required
from app.screens.forms import ScreenForm
from app.screens.models import Screen
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