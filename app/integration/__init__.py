"""
Integration module for cinema management system
Handles cross-module operations and data flow
"""

from flask import Blueprint

# Create blueprint
bp = Blueprint('integration', __name__)

# Import routes to register them
from . import routes

# Import service classes
from .service import IntegrationService
from .workflows import BookingWorkflow, ReportingWorkflow
from .search import GlobalSearchService
from .notifications import NotificationService

__all__ = [
    'bp',
    'IntegrationService',
    'BookingWorkflow', 
    'ReportingWorkflow',
    'GlobalSearchService',
    'NotificationService'
]