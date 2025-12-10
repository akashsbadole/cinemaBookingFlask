"""
Screens Blueprint
"""
from flask import Blueprint

bp = Blueprint('screens', __name__)

from app.screens import routes, models, forms