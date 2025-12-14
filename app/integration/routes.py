"""
Integration Routes for Cinema Management System
API endpoints for cross-module operations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta

from .service import IntegrationService
from .workflows import BookingWorkflow, ReportingWorkflow
from .search import GlobalSearchService
from .notifications import NotificationService, NotificationType, NotificationChannel, NotificationPriority

bp = Blueprint('integration', __name__, url_prefix='/api/integration')


# Dashboard and Statistics
@bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard_statistics():
    """Get comprehensive dashboard statistics"""
    try:
        stats = IntegrationService.get_dashboard_statistics()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        current_app.logger.error(f"Error getting dashboard statistics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Data Integrity
@bp.route('/integrity/check', methods=['GET'])
@login_required
def check_data_integrity():
    """Run comprehensive data integrity checks"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        integrity_results = IntegrationService.validate_data_integrity()
        return jsonify({'success': True, 'data': integrity_results})
    except Exception as e:
        current_app.logger.error(f"Error checking data integrity: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/integrity/fix', methods=['POST'])
@login_required
def fix_integrity_issues():
    """Fix common integrity issues"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        from app.data_integrity import IntegrityChecker
        fixes = IntegrityChecker.fix_orphaned_records()
        return jsonify({'success': True, 'data': fixes})
    except Exception as e:
        current_app.logger.error(f"Error fixing integrity issues: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Cross-Module Data
@bp.route('/data/<module_type>', methods=['GET'])
@login_required
def get_cross_module_data(module_type):
    """Get integrated data across multiple modules"""
    try:
        filters = request.args.to_dict()
        
        # Convert date strings to date objects
        if 'start_date' in filters:
            filters['start_date'] = datetime.strptime(filters['start_date'], '%Y-%m-%d').date()
        if 'end_date' in filters:
            filters['end_date'] = datetime.strptime(filters['end_date'], '%Y-%m-%d').date()
        
        data = IntegrationService.get_cross_module_data(module_type, filters)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting cross-module data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Booking Workflow
@bp.route('/booking/movies', methods=['GET'])
@login_required
def get_available_movies():
    """Get movies with available shows"""
    try:
        movie_date = request.args.get('date')
        if movie_date:
            movie_date = datetime.strptime(movie_date, '%Y-%m-%d').date()
        
        movies = BookingWorkflow.get_available_movies(movie_date)
        return jsonify({'success': True, 'data': movies})
    except Exception as e:
        current_app.logger.error(f"Error getting available movies: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/movies/<int:movie_id>/shows', methods=['GET'])
@login_required
def get_movie_shows(movie_id):
    """Get shows for a specific movie"""
    try:
        show_date = request.args.get('date')
        if show_date:
            show_date = datetime.strptime(show_date, '%Y-%m-%d').date()
        
        shows = BookingWorkflow.get_movie_shows(movie_id, show_date)
        return jsonify({'success': True, 'data': shows})
    except Exception as e:
        current_app.logger.error(f"Error getting movie shows: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/shows/<int:show_id>/seats', methods=['GET'])
@login_required
def get_show_seat_layout(show_id):
    """Get seat layout for a show"""
    try:
        seat_layout = BookingWorkflow.get_show_seat_layout(show_id)
        return jsonify({'success': True, 'data': seat_layout})
    except Exception as e:
        current_app.logger.error(f"Error getting show seat layout: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/reserve', methods=['POST'])
@login_required
def reserve_seats():
    """Reserve seats for a show"""
    try:
        data = request.get_json()
        show_id = data.get('show_id')
        seat_ids = data.get('seat_ids', [])
        lock_minutes = data.get('lock_minutes', 10)
        
        result = BookingWorkflow.reserve_seats(show_id, seat_ids, current_user.id, lock_minutes)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error reserving seats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/create', methods=['POST'])
@login_required
def create_booking():
    """Create a booking"""
    try:
        data = request.get_json()
        show_id = data.get('show_id')
        seat_ids = data.get('seat_ids', [])
        customer_info = data.get('customer_info', {})
        
        result = BookingWorkflow.create_booking(show_id, seat_ids, customer_info, current_user.id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error creating booking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/payment', methods=['POST'])
@login_required
def process_payment():
    """Process payment for a booking"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        payment_info = data.get('payment_info', {})
        
        result = BookingWorkflow.process_payment(booking_id, payment_info, current_user.id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error processing payment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/complete', methods=['POST'])
@login_required
def complete_booking():
    """Complete the entire booking workflow"""
    try:
        data = request.get_json()
        movie_id = data.get('movie_id')
        show_id = data.get('show_id')
        seat_ids = data.get('seat_ids', [])
        customer_info = data.get('customer_info', {})
        payment_info = data.get('payment_info', {})
        
        result = BookingWorkflow.complete_booking_workflow(
            movie_id, show_id, seat_ids, customer_info, payment_info, current_user.id
        )
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error completing booking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/booking/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    """Cancel a booking"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason')
        
        result = BookingWorkflow.cancel_booking(booking_id, current_user.id, reason)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error cancelling booking: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Reporting Workflow
@bp.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    """Generate comprehensive reports"""
    try:
        data = request.get_json()
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
        report_type = data.get('report_type', 'daily')
        
        report_data = ReportingWorkflow.generate_comprehensive_report(start_date, end_date, report_type)
        return jsonify({'success': True, 'data': report_data})
    except Exception as e:
        current_app.logger.error(f"Error generating report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/reports/export', methods=['POST'])
@login_required
def export_report():
    """Export report to CSV"""
    try:
        data = request.get_json()
        report_data = data.get('report_data')
        filename = data.get('filename')
        
        result = ReportingWorkflow.export_report_to_csv(report_data, filename)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error exporting report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Global Search
@bp.route('/search', methods=['GET'])
@login_required
def global_search():
    """Global search across all modules"""
    try:
        query = request.args.get('q', '')
        module_type = request.args.get('module', 'all')
        limit = int(request.args.get('limit', 20))
        
        filters = {
            'module_type': module_type,
            'limit': limit
        }
        
        # Add date range if provided
        if request.args.get('start_date'):
            filters['date_range'] = {
                'start_date': datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
            }
        if request.args.get('end_date'):
            if 'date_range' not in filters:
                filters['date_range'] = {}
            filters['date_range']['end_date'] = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')
        
        results = GlobalSearchService.search(query, filters)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        current_app.logger.error(f"Error in global search: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/search/advanced', methods=['POST'])
@login_required
def advanced_search():
    """Advanced search with multiple criteria"""
    try:
        search_params = request.get_json()
        
        # Convert date strings to date objects
        if 'start_date' in search_params and search_params['start_date']:
            search_params['start_date'] = datetime.strptime(search_params['start_date'], '%Y-%m-%d')
        if 'end_date' in search_params and search_params['end_date']:
            search_params['end_date'] = datetime.strptime(search_params['end_date'], '%Y-%m-%d')
        
        results = GlobalSearchService.advanced_search(search_params)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        current_app.logger.error(f"Error in advanced search: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/search/suggestions', methods=['GET'])
@login_required
def get_search_suggestions():
    """Get search suggestions for autocomplete"""
    try:
        query = request.args.get('q', '')
        module_type = request.args.get('module', 'all')
        limit = int(request.args.get('limit', 10))
        
        suggestions = GlobalSearchService.get_search_suggestions(query, module_type, limit)
        return jsonify({'success': True, 'data': suggestions})
    except Exception as e:
        current_app.logger.error(f"Error getting search suggestions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Notifications
@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get user notifications"""
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 50))
        
        notifications = NotificationService.get_user_notifications(current_user.id, unread_only, limit)
        return jsonify({
            'success': True,
            'data': [notification.to_dict() for notification in notifications]
        })
    except Exception as e:
        current_app.logger.error(f"Error getting notifications: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread notifications"""
    try:
        count = NotificationService.get_unread_count(current_user.id)
        return jsonify({'success': True, 'data': {'count': count}})
    except Exception as e:
        current_app.logger.error(f"Error getting unread count: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    try:
        from .notifications import Notification
        notification = Notification.query.get(notification_id)
        
        if not notification or notification.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Notification not found'}), 404
        
        notification.mark_as_read()
        return jsonify({'success': True, 'message': 'Notification marked as read'})
    except Exception as e:
        current_app.logger.error(f"Error marking notification as read: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    try:
        count = NotificationService.mark_all_as_read(current_user.id)
        return jsonify({'success': True, 'data': {'count': count}})
    except Exception as e:
        current_app.logger.error(f"Error marking all as read: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/notifications/create', methods=['POST'])
@login_required
def create_notification():
    """Create a new notification (admin only)"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        data = request.get_json()
        title = data.get('title')
        message = data.get('message')
        notification_type = NotificationType(data.get('notification_type'))
        channel = NotificationChannel(data.get('channel', 'in_app'))
        priority = NotificationPriority(data.get('priority', 'medium'))
        
        notification = NotificationService.create_notification(
            title=title,
            message=message,
            notification_type=notification_type,
            channel=channel,
            priority=priority,
            user_id=data.get('user_id'),
            email=data.get('email'),
            phone=data.get('phone'),
            related_entity_type=data.get('related_entity_type'),
            related_entity_id=data.get('related_entity_id'),
            action_url=data.get('action_url'),
            metadata=data.get('metadata'),
            expires_in_hours=data.get('expires_in_hours')
        )
        
        return jsonify({
            'success': True,
            'data': notification.to_dict() if notification else None
        })
    except Exception as e:
        current_app.logger.error(f"Error creating notification: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Cascade Operations
@bp.route('/cascade/delete/movie/<int:movie_id>', methods=['DELETE'])
@login_required
def cascade_delete_movie(movie_id):
    """Safely delete a movie with cascade operations"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        result = IntegrationService.cascade_delete_movie(movie_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error deleting movie: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/cascade/delete/screen/<int:screen_id>', methods=['DELETE'])
@login_required
def cascade_delete_screen(screen_id):
    """Safely delete a screen with cascade operations"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        result = IntegrationService.cascade_delete_screen(screen_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error deleting screen: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/cascade/delete/user/<int:user_id>', methods=['DELETE'])
@login_required
def cascade_delete_user(user_id):
    """Safely delete a user with cascade operations"""
    try:
        if not current_user.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        result = IntegrationService.cascade_delete_user(user_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# System Health
@bp.route('/health', methods=['GET'])
@login_required
def system_health():
    """Get system health status"""
    try:
        from app.data_integrity import IntegrityChecker
        
        # Run basic integrity checks
        integrity_status = IntegrityChecker.run_all_checks()
        
        # Check database connection
        from app.database import db
        db.session.execute('SELECT 1')
        db_status = 'connected'
        
        return jsonify({
            'success': True,
            'data': {
                'database': db_status,
                'integrity': integrity_status['summary'],
                'timestamp': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error checking system health: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500