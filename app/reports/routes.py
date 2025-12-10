"""
Reports Routes
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.reports import bp
from app.auth.decorators import admin_required

@bp.route('/')
@login_required
@admin_required
def index():
    """Reports dashboard"""
    return render_template('reports/index.html', title='Reports')

@bp.route('/daily_sales')
@login_required
@admin_required
def daily_sales():
    """Daily sales report"""
    return render_template('reports/daily_sales.html', title='Daily Sales Report')

@bp.route('/occupancy')
@login_required
@admin_required
def occupancy():
    """Seat occupancy report"""
    return render_template('reports/occupancy.html', title='Occupancy Report')

@bp.route('/cashier_summary')
@login_required
@admin_required
def cashier_summary():
    """Cashier performance summary"""
    return render_template('reports/cashier_summary.html', title='Cashier Summary')