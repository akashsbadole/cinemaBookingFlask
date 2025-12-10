"""
Payments Routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.payments import bp

@bp.route('/')
@login_required
def index():
    """Payments listing page"""
    return render_template('payments/index.html', title='Payments')

@bp.route('/process/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def process(booking_id):
    """Process payment for booking"""
    return render_template('payments/process.html', title='Process Payment')

@bp.route('/receipt/<int:id>')
@login_required
def receipt(id):
    """View payment receipt"""
    return render_template('payments/receipt.html', title='Payment Receipt')