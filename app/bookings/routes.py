"""
Bookings Routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.bookings import bp
from app.auth.decorators import admin_required

@bp.route('/')
@login_required
def index():
    """Bookings listing page"""
    return render_template('bookings/index.html', title='Bookings')

@bp.route('/new')
@login_required
def new():
    """Create new booking"""
    return render_template('bookings/new.html', title='New Booking')

@bp.route('/view/<int:id>')
@login_required
def view(id):
    """View booking details"""
    return render_template('bookings/view.html', title='Booking Details')

@bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    """Delete booking"""
    flash('Booking deleted successfully', 'success')
    return redirect(url_for('bookings.index'))