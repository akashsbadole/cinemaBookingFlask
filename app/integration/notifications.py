"""
Unified Notifications System for Cinema Management System
Handles notifications across all modules with different channels
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy import and_, or_, func
from flask import current_app

from app.database import db


class NotificationType(Enum):
    """Notification types"""
    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    SHOW_SCHEDULED = "show_scheduled"
    SHOW_CANCELLED = "show_cancelled"
    LOW_OCCUPANCY = "low_occupancy"
    HIGH_OCCUPANCY = "high_occupancy"
    SYSTEM_ALERT = "system_alert"
    DATA_INTEGRITY = "data_integrity"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"


class NotificationChannel(Enum):
    """Notification channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Notification(db.Model):
    """Notification model"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.Enum(NotificationType), nullable=False)
    channel = db.Column(db.Enum(NotificationChannel), nullable=False)
    priority = db.Column(db.Enum(NotificationPriority), default=NotificationPriority.MEDIUM)
    
    # Recipient information
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Null for system-wide notifications
    email = db.Column(db.String(120), nullable=True)  # For email notifications
    phone = db.Column(db.String(20), nullable=True)  # For SMS notifications
    
    # Status and timestamps
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_sent = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Related entity information
    related_entity_type = db.Column(db.String(50))  # booking, payment, show, etc.
    related_entity_id = db.Column(db.Integer)
    action_url = db.Column(db.String(255))  # URL for user to take action
    
    # Metadata
    notification_metadata = db.Column(db.Text)  # JSON string for additional data
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
    
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type.value,
            'channel': self.channel.value,
            'priority': self.priority.value,
            'user_id': self.user_id,
            'email': self.email,
            'phone': self.phone,
            'is_read': self.is_read,
            'is_sent': self.is_sent,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'action_url': self.action_url,
            'metadata': self.notification_metadata,
            'created_at': self.created_at.isoformat()
        }
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.is_sent = True
        self.sent_at = datetime.utcnow()
        db.session.commit()


class NotificationTemplate(db.Model):
    """Notification template model"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    notification_type = db.Column(db.Enum(NotificationType), nullable=False)
    channel = db.Column(db.Enum(NotificationChannel), nullable=False)
    subject_template = db.Column(db.String(200))  # For email notifications
    message_template = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<NotificationTemplate {self.name}>'


class NotificationService:
    """Unified notification service"""
    
    @staticmethod
    def create_notification(title: str, message: str, notification_type: NotificationType,
                         channel: NotificationChannel = NotificationChannel.IN_APP,
                         priority: NotificationPriority = NotificationPriority.MEDIUM,
                         user_id: int = None, email: str = None, phone: str = None,
                         related_entity_type: str = None, related_entity_id: int = None,
                         action_url: str = None, metadata: Dict[str, Any] = None,
                         expires_in_hours: int = None) -> Notification:
        """Create a new notification"""
        try:
            notification = Notification(
                title=title,
                message=message,
                notification_type=notification_type,
                channel=channel,
                priority=priority,
                user_id=user_id,
                email=email,
                phone=phone,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                action_url=action_url,
                notification_metadata=str(metadata) if metadata else None
            )
            
            if expires_in_hours:
                notification.expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
            
            db.session.add(notification)
            db.session.commit()
            
            # Send notification based on channel
            NotificationService._send_notification(notification)
            
            return notification
            
        except Exception as e:
            current_app.logger.error(f"Error creating notification: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def _send_notification(notification: Notification):
        """Send notification through appropriate channel"""
        try:
            if notification.channel == NotificationChannel.IN_APP:
                # In-app notifications are automatically available
                notification.mark_as_sent()
                
            elif notification.channel == NotificationChannel.EMAIL:
                # Send email notification
                NotificationService._send_email_notification(notification)
                
            elif notification.channel == NotificationChannel.SMS:
                # Send SMS notification
                NotificationService._send_sms_notification(notification)
                
            elif notification.channel == NotificationChannel.PUSH:
                # Send push notification
                NotificationService._send_push_notification(notification)
                
        except Exception as e:
            current_app.logger.error(f"Error sending notification: {str(e)}")
    
    @staticmethod
    def _send_email_notification(notification: Notification):
        """Send email notification"""
        try:
            # This would integrate with an email service like SendGrid, SES, etc.
            # For now, we'll just mark as sent
            notification.mark_as_sent()
            current_app.logger.info(f"Email notification sent: {notification.title}")
            
        except Exception as e:
            current_app.logger.error(f"Error sending email notification: {str(e)}")
    
    @staticmethod
    def _send_sms_notification(notification: Notification):
        """Send SMS notification"""
        try:
            # This would integrate with an SMS service like Twilio, etc.
            # For now, we'll just mark as sent
            notification.mark_as_sent()
            current_app.logger.info(f"SMS notification sent: {notification.title}")
            
        except Exception as e:
            current_app.logger.error(f"Error sending SMS notification: {str(e)}")
    
    @staticmethod
    def _send_push_notification(notification: Notification):
        """Send push notification"""
        try:
            # This would integrate with a push notification service
            # For now, we'll just mark as sent
            notification.mark_as_sent()
            current_app.logger.info(f"Push notification sent: {notification.title}")
            
        except Exception as e:
            current_app.logger.error(f"Error sending push notification: {str(e)}")
    
    @staticmethod
    def get_user_notifications(user_id: int, unread_only: bool = False, 
                             limit: int = 50) -> List[Notification]:
        """Get notifications for a user"""
        try:
            query = Notification.query.filter_by(user_id=user_id)
            
            if unread_only:
                query = query.filter_by(is_read=False)
            
            # Filter out expired notifications
            query = query.filter(
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.utcnow()
                )
            )
            
            return query.order_by(Notification.created_at.desc()).limit(limit).all()
            
        except Exception as e:
            current_app.logger.error(f"Error getting user notifications: {str(e)}")
            return []
    
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Get count of unread notifications for a user"""
        try:
            return Notification.query.filter_by(user_id=user_id, is_read=False).filter(
                or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.utcnow()
                )
            ).count()
            
        except Exception as e:
            current_app.logger.error(f"Error getting unread count: {str(e)}")
            return 0
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Mark all notifications as read for a user"""
        try:
            notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
            
            for notification in notifications:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
            
            db.session.commit()
            return len(notifications)
            
        except Exception as e:
            current_app.logger.error(f"Error marking all as read: {str(e)}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def delete_old_notifications(days_old: int = 30) -> int:
        """Delete old notifications"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = Notification.query.filter(
                Notification.created_at < cutoff_date
            ).delete()
            
            db.session.commit()
            return deleted_count
            
        except Exception as e:
            current_app.logger.error(f"Error deleting old notifications: {str(e)}")
            db.session.rollback()
            return 0
    
    # Module-specific notification methods
    
    @staticmethod
    def notify_booking_confirmed(booking_id: int, user_id: int = None):
        """Send notification for confirmed booking"""
        try:
            from app.bookings.models import Booking
            
            booking = Booking.query.get(booking_id)
            if not booking:
                return
            
            title = "Booking Confirmed"
            message = f"Your booking {booking.reference_number} has been confirmed for {booking.show.movie.name} on {booking.show.show_date} at {booking.show.show_time.strftime('%H:%M')}."
            
            NotificationService.create_notification(
                title=title,
                message=message,
                notification_type=NotificationType.BOOKING_CONFIRMED,
                user_id=user_id or booking.user_id,
                related_entity_type='booking',
                related_entity_id=booking.id,
                action_url=f'/bookings/view/{booking.id}'
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending booking confirmation: {str(e)}")
    
    @staticmethod
    def notify_booking_cancelled(booking_id: int, user_id: int = None):
        """Send notification for cancelled booking"""
        try:
            from app.bookings.models import Booking
            
            booking = Booking.query.get(booking_id)
            if not booking:
                return
            
            title = "Booking Cancelled"
            message = f"Your booking {booking.reference_number} has been cancelled."
            
            NotificationService.create_notification(
                title=title,
                message=message,
                notification_type=NotificationType.BOOKING_CANCELLED,
                user_id=user_id or booking.user_id,
                related_entity_type='booking',
                related_entity_id=booking.id,
                action_url=f'/bookings/view/{booking.id}'
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending booking cancellation: {str(e)}")
    
    @staticmethod
    def notify_payment_completed(payment_id: int):
        """Send notification for completed payment"""
        try:
            from app.payments.models import Payment
            
            payment = Payment.query.get(payment_id)
            if not payment:
                return
            
            title = "Payment Completed"
            message = f"Payment of ₹{payment.amount} has been completed for booking {payment.booking.reference_number}."
            
            NotificationService.create_notification(
                title=title,
                message=message,
                notification_type=NotificationType.PAYMENT_COMPLETED,
                user_id=payment.booking.user_id,
                related_entity_type='payment',
                related_entity_id=payment.id,
                action_url=f'/payments/view/{payment.id}'
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending payment completion: {str(e)}")
    
    @staticmethod
    def notify_payment_failed(payment_id: int):
        """Send notification for failed payment"""
        try:
            from app.payments.models import Payment
            
            payment = Payment.query.get(payment_id)
            if not payment:
                return
            
            title = "Payment Failed"
            message = f"Payment of ₹{payment.amount} has failed for booking {payment.booking.reference_number}. Please try again."
            
            NotificationService.create_notification(
                title=title,
                message=message,
                notification_type=NotificationType.PAYMENT_FAILED,
                priority=NotificationPriority.HIGH,
                user_id=payment.booking.user_id,
                related_entity_type='payment',
                related_entity_id=payment.id,
                action_url=f'/payments/view/{payment.id}'
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending payment failure: {str(e)}")
    
    @staticmethod
    def notify_low_occupancy(show_id: int, threshold: float = 20.0):
        """Send notification for low show occupancy"""
        try:
            from app.shows.models import Show
            
            show = Show.query.get(show_id)
            if not show:
                return
            
            occupancy = show.get_occupancy_percentage()
            if occupancy >= threshold:
                return
            
            title = "Low Show Occupancy Alert"
            message = f"Show '{show.movie.name}' in {show.screen.name} on {show.show_date} at {show.show_time.strftime('%H:%M')} has only {occupancy}% occupancy."
            
            # Send to all admin users
            from app.auth.models import User
            admin_users = User.query.filter_by(role='admin', is_active=True).all()
            
            for admin in admin_users:
                NotificationService.create_notification(
                    title=title,
                    message=message,
                    notification_type=NotificationType.LOW_OCCUPANCY,
                    user_id=admin.id,
                    related_entity_type='show',
                    related_entity_id=show.id,
                    action_url=f'/shows/view/{show.id}'
                )
            
        except Exception as e:
            current_app.logger.error(f"Error sending low occupancy alert: {str(e)}")
    
    @staticmethod
    def notify_system_alert(message: str, priority: NotificationPriority = NotificationPriority.MEDIUM):
        """Send system-wide alert"""
        try:
            title = "System Alert"
            
            # Send to all admin users
            from app.auth.models import User
            admin_users = User.query.filter_by(role='admin', is_active=True).all()
            
            for admin in admin_users:
                NotificationService.create_notification(
                    title=title,
                    message=message,
                    notification_type=NotificationType.SYSTEM_ALERT,
                    priority=priority,
                    user_id=admin.id,
                    expires_in_hours=24
                )
            
        except Exception as e:
            current_app.logger.error(f"Error sending system alert: {str(e)}")
    
    @staticmethod
    def notify_data_integrity_issue(issue_type: str, details: Dict[str, Any]):
        """Send notification for data integrity issues"""
        try:
            title = "Data Integrity Issue"
            message = f"Data integrity issue detected: {issue_type}"
            
            # Send to all admin users
            from app.auth.models import User
            admin_users = User.query.filter_by(role='admin', is_active=True).all()
            
            for admin in admin_users:
                NotificationService.create_notification(
                    title=title,
                    message=message,
                    notification_type=NotificationType.DATA_INTEGRITY,
                    priority=NotificationPriority.HIGH,
                    user_id=admin.id,
                    metadata=details,
                    expires_in_hours=48
                )
            
        except Exception as e:
            current_app.logger.error(f"Error sending data integrity notification: {str(e)}")
    
    @staticmethod
    def create_notification_template(name: str, notification_type: NotificationType,
                                   channel: NotificationChannel, subject_template: str = None,
                                   message_template: str = None):
        """Create a notification template"""
        try:
            template = NotificationTemplate(
                name=name,
                notification_type=notification_type,
                channel=channel,
                subject_template=subject_template,
                message_template=message_template
            )
            
            db.session.add(template)
            db.session.commit()
            
            return template
            
        except Exception as e:
            current_app.logger.error(f"Error creating notification template: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def get_notification_statistics(user_id: int = None) -> Dict[str, Any]:
        """Get notification statistics"""
        try:
            query = db.session.query(
                Notification.notification_type,
                Notification.priority,
                func.count(Notification.id).label('count')
            )
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            stats = query.group_by(Notification.notification_type, Notification.priority).all()
            
            result = {
                'by_type': {},
                'by_priority': {},
                'total': 0
            }
            
            for stat in stats:
                notification_type = stat.notification_type.value if stat.notification_type else 'unknown'
                priority = stat.priority.value if stat.priority else 'unknown'
                count = stat.count
                
                if notification_type not in result['by_type']:
                    result['by_type'][notification_type] = 0
                result['by_type'][notification_type] += count
                
                if priority not in result['by_priority']:
                    result['by_priority'][priority] = 0
                result['by_priority'][priority] += count
                
                result['total'] += count
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error getting notification statistics: {str(e)}")
            return {}