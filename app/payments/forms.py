"""
Payments Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, DecimalField, SubmitField, TextAreaField, IntegerField, EmailField, TelField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp, ValidationError
from wtforms.widgets import TextArea
import re
from datetime import datetime
from app.validators import (
    DataValidators, BusinessValidators, InputSanitizer,
    SecurityValidator, CrossFieldValidators
)
from app.enhanced_validators import (
    BusinessRuleValidators, ValidationAuditor
)
from app.payments.models import Payment


class PaymentMethodForm(FlaskForm):
    """Form for selecting payment method"""
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Digital Wallet')
    ], validators=[DataRequired(message='Please select a payment method')])
    amount_received = DecimalField('Amount Received', validators=[
        DataRequired(message='Amount is required'),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Payment')
    
    def validate_amount_received(self, field):
        """Validate and sanitize amount received with business rules"""
        if field.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(
                field.data,
                min_val=0.01,
                max_val=100000,  # Maximum reasonable amount
                decimal_places=2
            )
            
            if sanitized is None:
                raise ValidationError('Invalid amount format')
            
            # Validate payment method limits
            payment_method = self.payment_method.data if self.payment_method.data else None
            if payment_method:
                from flask_login import current_user
                user_id = current_user.id if current_user.is_authenticated else None
                
                payment_valid, payment_error = BusinessRuleValidators.validate_payment_method_limits(
                    user_id, payment_method, sanitized
                )
                
                if not payment_valid:
                    raise ValidationError(payment_error)
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class CashPaymentForm(FlaskForm):
    """Form for cash payment processing"""
    amount_received = DecimalField('Amount Received', validators=[
        DataRequired(message='Amount received is required'),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    amount_tendered = DecimalField('Amount Tendered', validators=[
        DataRequired(message='Amount tendered is required'),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    reference_id = StringField('Receipt Number', validators=[
        Optional(),
        Length(max=50, message='Receipt number cannot exceed 50 characters')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Cash Payment')
    
    def validate_amount_tendered(self, field):
        """Validate that tendered amount is sufficient"""
        if field.data and self.amount_received.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(
                field.data, 
                min_val=0.01, 
                decimal_places=2
            )
            
            if sanitized is None:
                raise ValidationError('Invalid amount format')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            if field.data < self.amount_received.data:
                raise ValidationError('Amount tendered must be at least the amount due')
    
    def validate_reference_id(self, field):
        """Validate and sanitize reference ID"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in receipt number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class CardPaymentForm(FlaskForm):
    """Form for card payment processing"""
    card_number = StringField('Card Number', validators=[
        DataRequired(message='Card number is required'),
        Regexp(r'^\d{13,19}$', message='Card number must be 13-19 digits')
    ])
    card_holder = StringField('Card Holder Name', validators=[
        DataRequired(message='Card holder name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    expiry_month = SelectField('Expiry Month', choices=[
        (str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)
    ], validators=[DataRequired(message='Expiry month is required')])
    expiry_year = SelectField('Expiry Year', choices=[
        (str(i), str(i)) for i in range(datetime.now().year, datetime.now().year + 10)
    ], validators=[DataRequired(message='Expiry year is required')])
    cvv = StringField('CVV', validators=[
        DataRequired(message='CVV is required'),
        Regexp(r'^\d{3,4}$', message='CVV must be 3-4 digits')
    ])
    card_type = SelectField('Card Type', choices=[
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
        ('amex', 'American Express'),
        ('discover', 'Discover'),
        ('other', 'Other')
    ], validators=[DataRequired(message='Card type is required')])
    reference_id = StringField('Authorization Code', validators=[
        Optional(),
        Length(max=50, message='Authorization code cannot exceed 50 characters')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Card Payment')
    
    def validate_card_number(self, field):
        """Validate and sanitize card number"""
        if field.data:
            # Remove spaces and dashes for validation
            clean_number = field.data.replace(' ', '').replace('-', '')
            
            # Use our centralized card validator
            is_valid, error_message, card_type = DataValidators.validate_card_number(clean_number)
            
            if not is_valid:
                raise ValidationError(error_message)
            
            # Update card type if auto-detected
            if self.card_type.data == 'other' and card_type != 'other':
                self.card_type.data = card_type
            
            # Update field data with clean version
            field.data = clean_number
    
    def validate_card_holder(self, field):
        """Validate and sanitize card holder name"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in card holder name')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in card holder name')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_cvv(self, field):
        """Validate CVV based on card type"""
        if field.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(field.data)
            
            if sanitized is None or len(str(sanitized)) > 4:
                raise ValidationError('CVV must be 3-4 digits')
            
            # Additional validation for American Express
            if self.card_type.data == 'amex' and len(str(sanitized)) != 4:
                raise ValidationError('American Express cards require 4-digit CVV')
            elif self.card_type.data != 'amex' and len(str(sanitized)) != 3:
                raise ValidationError('CVV must be 3 digits for this card type')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_expiry(self):
        """Validate that card is not expired"""
        if self.expiry_month.data and self.expiry_year.data:
            try:
                expiry_date = datetime(int(self.expiry_year.data), int(self.expiry_month.data), 1)
                if expiry_date < datetime.now():
                    raise ValidationError('Card has expired')
            except ValueError:
                raise ValidationError('Invalid expiry date')


class UpiPaymentForm(FlaskForm):
    """Form for UPI payment processing"""
    upi_id = StringField('UPI ID', validators=[
        DataRequired(message='UPI ID is required'),
        Regexp(r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$', message='Invalid UPI ID format')
    ])
    transaction_id = StringField('Transaction ID', validators=[
        DataRequired(message='Transaction ID is required'),
        Length(min=6, max=50, message='Transaction ID must be 6-50 characters')
    ])
    reference_id = StringField('UTR Number', validators=[
        Optional(),
        Length(max=50, message='UTR cannot exceed 50 characters')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process UPI Payment')
    
    def validate_upi_id(self, field):
        """Validate and sanitize UPI ID"""
        if field.data:
            # Use our centralized UPI validator
            is_valid, error_message = DataValidators.validate_upi_id(field.data)
            
            if not is_valid:
                raise ValidationError(error_message)
            
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in UPI ID')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_transaction_id(self, field):
        """Validate and sanitize transaction ID"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in transaction ID')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_reference_id(self, field):
        """Validate and sanitize UTR number"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in UTR number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class NetBankingPaymentForm(FlaskForm):
    """Form for net banking payment processing"""
    bank_name = SelectField('Bank Name', choices=[
        ('sbi', 'State Bank of India'),
        ('hdfc', 'HDFC Bank'),
        ('icici', 'ICICI Bank'),
        ('pnb', 'Punjab National Bank'),
        ('axis', 'Axis Bank'),
        ('kotak', 'Kotak Mahindra Bank'),
        ('bob', 'Bank of Baroda'),
        ('canara', 'Canara Bank'),
        ('union', 'Union Bank of India'),
        ('indian', 'Indian Bank'),
        ('other', 'Other Bank')
    ], validators=[DataRequired(message='Please select a bank')])
    transaction_id = StringField('Transaction Reference', validators=[
        DataRequired(message='Transaction reference is required'),
        Length(min=6, max=50, message='Transaction reference must be 6-50 characters')
    ])
    account_last_4 = StringField('Account Last 4 Digits', validators=[
        DataRequired(message='Account last 4 digits are required'),
        Regexp(r'^\d{4}$', message='Account last 4 digits must be exactly 4 digits')
    ])
    reference_id = StringField('Bank Reference', validators=[
        Optional(),
        Length(max=50, message='Bank reference cannot exceed 50 characters')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Net Banking Payment')
    
    def validate_transaction_id(self, field):
        """Validate and sanitize transaction reference"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in transaction reference')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_account_last_4(self, field):
        """Validate and sanitize account last 4 digits"""
        if field.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(field.data)
            
            if sanitized is None or len(str(sanitized)) != 4:
                raise ValidationError('Account last 4 digits must be exactly 4 digits')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_reference_id(self, field):
        """Validate and sanitize bank reference"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in bank reference')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class WalletPaymentForm(FlaskForm):
    """Form for digital wallet payment processing"""
    wallet_type = SelectField('Wallet Type', choices=[
        ('paytm', 'PayTM'),
        ('phonepe', 'PhonePe'),
        ('googlepay', 'Google Pay'),
        ('amazonpay', 'Amazon Pay'),
        ('mobikwik', 'MobiKwik'),
        ('freecharge', 'FreeCharge'),
        ('airtel', 'Airtel Money'),
        ('jio', 'JioMoney'),
        ('other', 'Other Wallet')
    ], validators=[DataRequired(message='Please select a wallet type')])
    mobile_number = StringField('Registered Mobile Number', validators=[
        DataRequired(message='Mobile number is required'),
        Regexp(r'^\d{10}$', message='Mobile number must be exactly 10 digits')
    ])
    transaction_id = StringField('Transaction ID', validators=[
        DataRequired(message='Transaction ID is required'),
        Length(min=6, max=50, message='Transaction ID must be 6-50 characters')
    ])
    reference_id = StringField('Wallet Reference', validators=[
        Optional(),
        Length(max=50, message='Wallet reference cannot exceed 50 characters')
    ])
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Wallet Payment')
    
    def validate_mobile_number(self, field):
        """Validate and sanitize mobile number"""
        if field.data:
            # Sanitize phone number
            sanitized = InputSanitizer.sanitize_phone(field.data)
            
            if not sanitized:
                raise ValidationError('Please enter a valid 10-digit mobile number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_transaction_id(self, field):
        """Validate and sanitize transaction ID"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in transaction ID')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_reference_id(self, field):
        """Validate and sanitize wallet reference"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=50)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in wallet reference')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class RefundPaymentForm(FlaskForm):
    """Form for processing payment refunds"""
    refund_amount = DecimalField('Refund Amount', validators=[
        DataRequired(message='Refund amount is required'),
        NumberRange(min=0.01, message='Refund amount must be greater than 0')
    ], places=2)
    refund_reason = SelectField('Refund Reason', choices=[
        ('customer_request', 'Customer Request'),
        ('show_cancelled', 'Show Cancelled'),
        ('technical_issue', 'Technical Issue'),
        ('double_payment', 'Double Payment'),
        ('other', 'Other Reason')
    ], validators=[DataRequired(message='Please select a refund reason')])
    refund_notes = TextAreaField('Refund Notes', validators=[
        DataRequired(message='Refund notes are required'),
        Length(min=5, max=500, message='Notes must be between 5 and 500 characters')
    ])
    refund_method = SelectField('Refund Method', choices=[
        ('original', 'Same as Original Payment'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('wallet', 'Wallet Credit')
    ], validators=[DataRequired(message='Please select a refund method')])
    submit = SubmitField('Process Refund')
    
    def __init__(self, original_amount=None, *args, **kwargs):
        super(RefundPaymentForm, self).__init__(*args, **kwargs)
        self.original_amount = original_amount
    
    def validate_refund_amount(self, field):
        """Validate refund amount against original payment"""
        if field.data and self.original_amount:
            # Use our centralized refund validator
            is_valid, error_message = BusinessValidators.validate_refund_eligibility(
                type('MockPayment', {'amount': self.original_amount}),  # Mock payment object
                field.data
            )
            
            if not is_valid:
                raise ValidationError(error_message)
            
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(
                field.data, 
                max_val=float(self.original_amount), 
                decimal_places=2
            )
            
            if sanitized is None:
                raise ValidationError('Invalid refund amount format')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_refund_notes(self, field):
        """Validate and sanitize refund notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in refund notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class PaymentStatusForm(FlaskForm):
    """Form for updating payment status"""
    status = SelectField('Payment Status', choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled')
    ], validators=[DataRequired(message='Please select a status')])
    notes = TextAreaField('Status Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Update Status')
    
    def validate_notes(self, field):
        """Validate and sanitize status notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in status notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class PaymentSearchForm(FlaskForm):
    """Form for searching payments with enhanced validation"""
    search_term = StringField('Search', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    search_type = SelectField('Search By', choices=[
        ('all', 'All Fields'),
        ('transaction_id', 'Transaction ID'),
        ('booking_id', 'Booking ID'),
        ('customer', 'Customer Name'),
        ('payment_method', 'Payment Method')
    ], default='all')
    status_filter = SelectField('Status Filter', choices=[
        ('all', 'All Status'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled')
    ], default='all')
    payment_method_filter = SelectField('Payment Method Filter', choices=[
        ('all', 'All Methods'),
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Digital Wallet')
    ], default='all')
    date_from = StringField('From Date', validators=[Optional()])
    date_to = StringField('To Date', validators=[Optional()])
    submit = SubmitField('Search')
    
    def validate_search_term(self, field):
        """Validate and sanitize search term"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_date_range(self):
        """Validate date range"""
        date_from = self.date_from.data
        date_to = self.date_to.data
        
        if date_from and date_to:
            try:
                # Parse dates (assuming YYYY-MM-DD format)
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # Use our centralized date range validator
                is_valid, error_message = DataValidators.validate_date_range(from_date, to_date, 365)
                
                if not is_valid:
                    raise ValidationError(error_message)
                    
            except ValueError:
                raise ValidationError('Invalid date format. Please use YYYY-MM-DD format')


class PaymentForm(FlaskForm):
    """General payment form for payment processing"""
    booking_id = HiddenField('Booking ID')
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Digital Wallet')
    ], validators=[DataRequired(message='Please select a payment method')])
    amount = DecimalField('Amount', validators=[
        DataRequired(message='Amount is required'),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    notes = TextAreaField('Notes', validators=[
        Optional(),
        Length(max=500, message='Notes cannot exceed 500 characters')
    ])
    submit = SubmitField('Process Payment')
    
    def validate_amount(self, field):
        """Validate payment amount"""
        if field.data:
            # Sanitize numeric input
            sanitized = InputSanitizer.sanitize_numeric(
                field.data, 
                min_val=0.01, 
                max_val=100000,  # Maximum reasonable amount
                decimal_places=2
            )
            
            if sanitized is None:
                raise ValidationError('Invalid amount format')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_notes(self, field):
        """Validate and sanitize notes"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in notes')
            
            # Update field data with sanitized version
            field.data = sanitized


class EmailReceiptForm(FlaskForm):
    """Form for sending payment receipt via email"""
    email = StringField('Email Address', validators=[
        DataRequired(message='Email address is required'),
        Length(max=255, message='Email address cannot exceed 255 characters')
    ])
    message = TextAreaField('Additional Message', validators=[
        Optional(),
        Length(max=500, message='Message cannot exceed 500 characters')
    ])
    submit = SubmitField('Send Receipt')
    
    def validate_email(self, field):
        """Validate and sanitize email address"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            
            if not sanitized:
                raise ValidationError('Invalid email address')
            
            # Update field data with sanitized version
            field.data = sanitized


class AdvancedPaymentSearchForm(FlaskForm):
    """Advanced search form for payments with comprehensive filtering"""
    # Basic search
    search_term = StringField('Search Term', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    search_type = SelectField('Search By', choices=[
        ('all', 'All Fields'),
        ('transaction_id', 'Transaction ID'),
        ('booking_id', 'Booking ID'),
        ('reference_id', 'Reference ID'),
        ('customer', 'Customer Name'),
        ('customer_email', 'Customer Email'),
        ('customer_phone', 'Customer Phone'),
        ('payment_method', 'Payment Method')
    ], default='all')
    
    # Date range
    date_from = StringField('From Date', validators=[Optional()])
    date_to = StringField('To Date', validators=[Optional()])
    
    # Status and method filters
    status = SelectField('Payment Status', choices=[
        ('', 'All Status'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled')
    ], validators=[Optional()])
    
    payment_method = SelectField('Payment Method', choices=[
        ('', 'All Methods'),
        ('cash', 'Cash'),
        ('card', 'Credit/Debit Card'),
        ('upi', 'UPI'),
        ('paypal', 'PayPal'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Digital Wallet')
    ], validators=[Optional()])
    
    # Amount range
    amount_min = DecimalField('Min Amount', validators=[
        Optional(),
        NumberRange(min=0, message='Amount must be positive')
    ], places=2)
    amount_max = DecimalField('Max Amount', validators=[
        Optional(),
        NumberRange(min=0, message='Amount must be positive')
    ], places=2)
    
    # Customer filters
    customer_name = StringField('Customer Name', validators=[
        Optional(),
        Length(max=100, message='Name cannot exceed 100 characters')
    ])
    customer_email = EmailField('Customer Email', validators=[Optional()])
    customer_phone = TelField('Customer Phone', validators=[Optional()])
    
    # Booking and transaction filters
    booking_id = IntegerField('Booking ID', validators=[Optional()])
    reference_id = StringField('Reference ID', validators=[
        Optional(),
        Length(max=100, message='Reference ID cannot exceed 100 characters')
    ])
    transaction_id = StringField('Transaction ID', validators=[
        Optional(),
        Length(max=100, message='Transaction ID cannot exceed 100 characters')
    ])
    
    # Sorting and pagination
    sort_by = SelectField('Sort By', choices=[
        ('created_at_desc', 'Payment Date (Newest)'),
        ('created_at_asc', 'Payment Date (Oldest)'),
        ('amount_desc', 'Amount (High to Low)'),
        ('amount_asc', 'Amount (Low to High)'),
        ('booking_id_desc', 'Booking ID (High to Low)'),
        ('booking_id_asc', 'Booking ID (Low to High)'),
        ('customer_name_asc', 'Customer Name (A-Z)'),
        ('customer_name_desc', 'Customer Name (Z-A)'),
        ('payment_method_asc', 'Payment Method (A-Z)'),
        ('payment_method_desc', 'Payment Method (Z-A)'),
        ('status_asc', 'Status (A-Z)'),
        ('status_desc', 'Status (Z-A)')
    ], default='created_at_desc')
    
    per_page = SelectField('Per Page', choices=[
        (10, '10'),
        (20, '20'),
        (50, '50'),
        (100, '100')
    ], default=20, coerce=int)
    
    # Form actions
    submit = SubmitField('Search')
    save_search = SubmitField('Save Search')
    clear = SubmitField('Clear')
    
    def validate_search_term(self, field):
        """Validate and sanitize search term"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_name(self, field):
        """Validate and sanitize customer name"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in customer name')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_email(self, field):
        """Validate customer email"""
        if field.data:
            # Sanitize email
            sanitized = InputSanitizer.sanitize_email(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid email address')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_customer_phone(self, field):
        """Validate customer phone"""
        if field.data:
            # Sanitize phone number
            sanitized = InputSanitizer.sanitize_phone(field.data)
            if not sanitized:
                raise ValidationError('Please enter a valid phone number')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_booking_id(self, field):
        """Validate booking ID"""
        if field.data and field.data > 0:
            # Validate booking ID is reasonable
            if field.data > 999999:
                raise ValidationError('Invalid booking ID')
    
    def validate_reference_id(self, field):
        """Validate and sanitize reference ID"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in reference ID')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_transaction_id(self, field):
        """Validate and sanitize transaction ID"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in transaction ID')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_date_range(self):
        """Validate date range"""
        date_from = self.date_from.data
        date_to = self.date_to.data
        
        if date_from and date_to:
            try:
                # Parse dates (assuming YYYY-MM-DD format)
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                if from_date > to_date:
                    raise ValidationError('From date cannot be after to date')
                
                # Limit date range to 1 year
                if (to_date - from_date).days > 365:
                    raise ValidationError('Date range cannot exceed 1 year')
                
            except ValueError:
                raise ValidationError('Invalid date format. Use YYYY-MM-DD format.')
    
    def validate_amount_range(self):
        """Validate amount range"""
        amount_min = self.amount_min.data
        amount_max = self.amount_max.data
        
        if amount_min is not None and amount_max is not None:
            if amount_min > amount_max:
                raise ValidationError('Minimum amount cannot be greater than maximum amount')
    
    def validate_message(self, field):
        """Validate and sanitize additional message"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em'],
                max_length=500
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in message')
            
            # Update field data with sanitized version
            field.data = sanitized
