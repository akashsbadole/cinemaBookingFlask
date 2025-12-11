"""
Shows Module
"""
from flask import Blueprint

# Create the shows blueprint
bp = Blueprint('shows', __name__)

# Import routes at the end to avoid circular imports
from app.shows import routes