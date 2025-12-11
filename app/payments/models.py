"""
Payments Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Payment(db.Model):
    """Payment model"""
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    mode = db.Column(db.Enum('cash', 'card', 'upi', 'paypal', 'netbanking', 'wallet', name='payment_modes'), nullable=False)
    reference_id = db.Column(db.String(50))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # PayPal specific fields
    paypal_order_id = db.Column(db.String(50))
    paypal_capture_id = db.Column(db.String(50))
    paypal_payment_status = db.Column(db.String(20))
    
    # Payment status and workflow
    status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed', 'refunded', 'cancelled', name='payment_status'), default='pending')
    notes = db.Column(db.Text)
    
    # Payment processing timestamps
    initiated_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    refunded_at = db.Column(db.DateTime)
    
    # Card payment specific fields
    card_type = db.Column(db.String(20))
    card_last_4 = db.Column(db.String(4))
    card_expiry_month = db.Column(db.String(2))
    card_expiry_year = db.Column(db.String(4))
    card_authorization_code = db.Column(db.String(50))
    
    # UPI payment specific fields
    upi_id = db.Column(db.String(100))
    upi_transaction_id = db.Column(db.String(50))
    utr_number = db.Column(db.String(50))
    
    # Net Banking specific fields
    bank_name = db.Column(db.String(50))
    netbanking_transaction_id = db.Column(db.String(50))
    account_last_4 = db.Column(db.String(4))
    
    # Wallet payment specific fields
    wallet_type = db.Column(db.String(30))
    wallet_mobile = db.Column(db.String(10))
    wallet_transaction_id = db.Column(db.String(50))
    
    # Refund specific fields
    refund_amount = db.Column(db.Numeric(10, 2))
    refund_reason = db.Column(db.String(100))
    refund_method = db.Column(db.String(30))
    refund_reference_id = db.Column(db.String(50))
    refund_notes = db.Column(db.Text)
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    refund_payments = db.relationship('PaymentRefund', backref='original_payment', lazy=True)
    status_history = db.relationship('PaymentStatusHistory', backref='payment', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Payment {self.id}>'
    
    def mark_processing(self):
        """Mark payment as processing"""
        self.status = 'processing'
        self.processed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._add_status_history('processing', 'Payment moved to processing')
    
    def mark_completed(self, transaction_id=None):
        """Mark payment as completed"""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if transaction_id:
            self.reference_id = transaction_id
        self._add_status_history('completed', 'Payment completed successfully')
    
    def mark_failed(self, reason=None):
        """Mark payment as failed"""
        self.status = 'failed'
        self.failed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._add_status_history('failed', f'Payment failed: {reason}' if reason else 'Payment failed')
    
    def mark_refunded(self, refund_amount=None, refund_reason=None, refund_method=None, refund_reference_id=None):
        """Mark payment as refunded"""
        self.status = 'refunded'
        self.refunded_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if refund_amount:
            self.refund_amount = refund_amount
        if refund_reason:
            self.refund_reason = refund_reason
        if refund_method:
            self.refund_method = refund_method
        if refund_reference_id:
            self.refund_reference_id = refund_reference_id
        self._add_status_history('refunded', f'Payment refunded: {refund_reason}' if refund_reason else 'Payment refunded')
    
    def mark_cancelled(self, reason=None):
        """Mark payment as cancelled"""
        self.status = 'cancelled'
        self.updated_at = datetime.utcnow()
        self._add_status_history('cancelled', f'Payment cancelled: {reason}' if reason else 'Payment cancelled')
    
    def _add_status_history(self, status, notes=None):
        """Add status change to history"""
        history = PaymentStatusHistory(
            payment_id=self.id,
            status=status,
            notes=notes,
            changed_at=datetime.utcnow()
        )
        self.status_history.append(history)
    
    def is_completed(self):
        """Check if payment is completed"""
        return self.status == 'completed'
    
    def is_failed(self):
        """Check if payment is failed"""
        return self.status == 'failed'
    
    def is_refunded(self):
        """Check if payment is refunded"""
        return self.status == 'refunded'
    
    def is_pending(self):
        """Check if payment is pending"""
        return self.status == 'pending'
    
    def is_processing(self):
        """Check if payment is processing"""
        return self.status == 'processing'
    
    def can_be_refunded(self):
        """Check if payment can be refunded"""
        return self.status == 'completed' and not self.is_refunded()
    
    def get_payment_method_display(self):
        """Get display name for payment method"""
        methods = {
            'cash': 'Cash',
            'card': 'Credit/Debit Card',
            'upi': 'UPI',
            'paypal': 'PayPal',
            'netbanking': 'Net Banking',
            'wallet': 'Digital Wallet'
        }
        return methods.get(self.mode, self.mode.title())
    
    def get_status_display(self):
        """Get display name for payment status"""
        statuses = {
            'pending': 'Pending',
            'processing': 'Processing',
            'completed': 'Completed',
            'failed': 'Failed',
            'refunded': 'Refunded',
            'cancelled': 'Cancelled'
        }
        return statuses.get(self.status, self.status.title())
    
    def get_status_badge_class(self):
        """Get Bootstrap badge class for payment status"""
        badge_classes = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'failed': 'danger',
            'refunded': 'secondary',
            'cancelled': 'dark'
        }
        return badge_classes.get(self.status, 'light')


class PaymentStatusHistory(db.Model):
    """Model for tracking payment status changes"""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed', 'refunded', 'cancelled', name='history_payment_status'), nullable=False)
    notes = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    changed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<PaymentStatusHistory {self.id}: {self.payment_id} -> {self.status}>'


class PaymentRefund(db.Model):
    """Model for tracking payment refunds"""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=False)
    refund_reason = db.Column(db.String(100), nullable=False)
    refund_method = db.Column(db.String(30), nullable=False)
    refund_reference_id = db.Column(db.String(50))
    refund_notes = db.Column(db.Text)
    refund_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<PaymentRefund {self.id}: {self.payment_id} -> {self.refund_amount}>'


class PaymentAudit(db.Model):
    """Model for auditing payment operations"""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    operation = db.Column(db.String(50), nullable=False)  # CREATE, UPDATE, DELETE, REFUND, etc.
    old_values = db.Column(db.Text)  # JSON string of old values
    new_values = db.Column(db.Text)  # JSON string of new values
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PaymentAudit {self.id}: {self.operation} on Payment {self.payment_id}>'
    
    @staticmethod
    def log_operation(payment_id, operation, user_id=None, old_values=None, new_values=None, ip_address=None, user_agent=None):
        """Log a payment operation"""
        import json
        
        audit = PaymentAudit(
            payment_id=payment_id,
            operation=operation,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.session.add(audit)
        return audit