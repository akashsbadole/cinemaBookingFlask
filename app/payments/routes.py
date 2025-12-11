"""
Payments Routes
"""
from flask import render_template, redirect, url_for, flash, request, make_response, jsonify, session, current_app, abort
from flask_login import login_required, current_user
from app.payments import bp
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment, PaymentStatusHistory, PaymentRefund, PaymentAudit
from app.payments.forms import (
    PaymentMethodForm, CashPaymentForm, CardPaymentForm, UpiPaymentForm,
    NetBankingPaymentForm, WalletPaymentForm, RefundPaymentForm,
    PaymentStatusForm, PaymentSearchForm, PaymentForm, EmailReceiptForm
)
from app.database import db
from app.utils import generate_receipt_pdf
from app.paypal_service import get_paypal_service
from app.validators import InputSanitizer, DataValidators, SecurityValidator, BusinessValidators, ValidationError
from app.error_handlers import ErrorLogger, ErrorHandler
from app.data_integrity import IntegrityChecker
from datetime import datetime, timedelta
import logging
import json
from flask_mail import Message, Mail

# Configure logging
logger = logging.getLogger(__name__)

def send_receipt_email(payment, recipient_email, message=None):
    """
    Send payment receipt via email with validation
    
    Args:
        payment (Payment): Payment object
        recipient_email (str): Email address to send receipt to
        message (str): Optional additional message
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Validate recipient email
        if not DataValidators.validate_email_format(recipient_email):
            logger.error(f"Invalid recipient email format: {recipient_email}")
            return False
        
        # Sanitize email address
        recipient_email = InputSanitizer.sanitize_email(recipient_email)
        
        # Validate payment object
        if not payment or not payment.id:
            logger.error("Invalid payment object for email receipt")
            return False
        
        # Get seats for this booking
        seats = []
        if payment.booking:
            for booking_seat in payment.booking.booking_seats:
                seats.append(f"{booking_seat.seat.row}{booking_seat.seat.column}")
        
        # Sanitize additional message
        safe_message = InputSanitizer.sanitize_string(message or "", max_length=500) if message else ""
        
        # Create email message
        msg = Message(
            subject=f"Cinema POS - Payment Receipt #{payment.id}",
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@cinemapos.com'),
            recipients=[recipient_email]
        )
        
        # Generate HTML email body
        msg.html = render_template('payments/email_receipt.html',
                                payment=payment,
                                seats=', '.join(seats),
                                message=safe_message)
        
        # Generate PDF receipt and attach it
        pdf_data = generate_receipt_pdf({
            'id': payment.id,
            'customer_name': InputSanitizer.sanitize_string(payment.booking.customer_name, max_length=100) if payment.booking else 'N/A',
            'contact_number': InputSanitizer.sanitize_string(payment.booking.contact_number, max_length=20) if payment.booking else 'N/A',
            'email': InputSanitizer.sanitize_email(payment.booking.email) if payment.booking else 'N/A',
            'booking_id': payment.booking_id,
            'movie_title': InputSanitizer.sanitize_string(payment.booking.show.movie.title, max_length=200) if payment.booking and payment.booking.show and payment.booking.show.movie else 'N/A',
            'screen_name': InputSanitizer.sanitize_string(payment.booking.show.screen.name, max_length=100) if payment.booking and payment.booking.show and payment.booking.show.screen else 'N/A',
            'show_date': payment.booking.show.show_date.strftime('%d %b %Y') if payment.booking and payment.booking.show and payment.booking.show.show_date else 'N/A',
            'show_time': payment.booking.show.show_time.strftime('%H:%M') if payment.booking and payment.booking.show and payment.booking.show.show_time else 'N/A',
            'seats': ', '.join(seats),
            'amount': float(payment.amount) if payment.amount else 0,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': InputSanitizer.sanitize_string(payment.reference_id, max_length=100),
            'paypal_order_id': InputSanitizer.sanitize_string(payment.paypal_order_id, max_length=100),
            'payment_date': payment.payment_date,
            'notes': InputSanitizer.sanitize_string(payment.notes, max_length=500) if payment.notes else '',
            'status': payment.get_status_display()
        })
        
        msg.attach(
            filename=f"receipt_{payment.id}.pdf",
            content_type="application/pdf",
            data=pdf_data
        )
        
        # Send email
        mail = Mail(current_app)
        mail.send(msg)
        
        ErrorLogger.log_security_event(
            'receipt_email_sent',
            f'Receipt email sent to {recipient_email} for payment {payment.id}',
            request,
            user_id=current_user.id,
            context={'payment_id': payment.id, 'recipient_email': recipient_email}
        )
        
        logger.info(f"Receipt email sent to {recipient_email} for payment {payment.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending receipt email: {str(e)}")
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment.id if payment else None})
        return False

@bp.route('/')
@login_required
def index():
    """Payments listing page with filtering and search with enhanced validation"""
    try:
        # Get search parameters
        search_form = PaymentSearchForm(request.args)
        
        # Build base query
        query = Payment.query
        
        # Sanitize and validate search parameters
        search_term = InputSanitizer.sanitize_string(search_form.search_term.data, max_length=100) if search_form.search_term.data else ""
        search_type = InputSanitizer.sanitize_string(search_form.search_type.data, max_length=20) if search_form.search_type.data else "all"
        status_filter = InputSanitizer.sanitize_string(search_form.status_filter.data, max_length=20) if search_form.status_filter.data else "all"
        payment_method_filter = InputSanitizer.sanitize_string(search_form.payment_method_filter.data, max_length=20) if search_form.payment_method_filter.data else "all"
        
        # Security check for injection attempts
        if SecurityValidator.detect_sql_injection([search_term, search_type, status_filter, payment_method_filter]):
            ErrorLogger.log_security_event(
                'sql_injection_attempt',
                f'SQL injection attempt detected in payment search: {search_term}',
                request,
                user_id=current_user.id,
                severity='high'
            )
            abort(400, "Invalid input detected")
        
        # Validate search type
        valid_search_types = ['all', 'transaction_id', 'booking_id', 'customer', 'payment_method']
        if search_type not in valid_search_types:
            search_type = 'all'
        
        # Apply search filters
        if search_term and search_type != 'all':
            search_term_safe = f"%{search_term}%"
            if search_type == 'transaction_id':
                query = query.filter(Payment.reference_id.like(search_term_safe))
            elif search_type == 'booking_id':
                try:
                    booking_id = int(search_term)
                    if booking_id > 0:
                        query = query.filter(Payment.booking_id == booking_id)
                    else:
                        query = query.join(Booking).filter(Booking.reference_number.like(search_term_safe))
                except ValueError:
                    query = query.join(Booking).filter(Booking.reference_number.like(search_term_safe))
            elif search_type == 'customer':
                query = query.join(Booking).filter(Booking.customer_name.like(search_term_safe))
            elif search_type == 'payment_method':
                query = query.filter(Payment.mode.like(search_term_safe))
        elif search_term:
            # Search across all fields
            search_term_safe = f"%{search_term}%"
            query = query.filter(
                db.or_(
                    Payment.reference_id.like(search_term_safe),
                    Payment.notes.like(search_term_safe),
                    Booking.customer_name.like(search_term_safe),
                    Booking.reference_number.like(search_term_safe)
                )
            )
        
        # Validate and apply status filter
        valid_statuses = ['all', 'pending', 'processing', 'completed', 'failed', 'refunded']
        if status_filter in valid_statuses and status_filter != 'all':
            query = query.filter(Payment.status == status_filter)
        
        # Validate and apply payment method filter
        valid_methods = ['all', 'cash', 'card', 'upi', 'netbanking', 'wallet', 'paypal']
        if payment_method_filter in valid_methods and payment_method_filter != 'all':
            query = query.filter(Payment.mode == payment_method_filter)
        
        # Apply date filters with validation
        if search_form.date_from.data:
            try:
                date_from = datetime.strptime(search_form.date_from.data, '%Y-%m-%d')
                if date_from <= datetime.now():
                    query = query.filter(Payment.created_at >= date_from)
                else:
                    flash('Start date cannot be in the future', 'warning')
            except ValueError:
                flash('Invalid start date format', 'warning')
        
        if search_form.date_to.data:
            try:
                date_to = datetime.strptime(search_form.date_to.data, '%Y-%m-%d')
                date_to = date_to + timedelta(days=1)  # Include the entire day
                query = query.filter(Payment.created_at < date_to)
            except ValueError:
                flash('Invalid end date format', 'warning')
        
        # Get payments with related data
        payments = query.order_by(Payment.created_at.desc()).limit(1000).all()  # Limit to prevent performance issues
        
        # Format payment data for template
        formatted_payments = []
        for payment in payments:
            try:
                # Get seats for this booking
                seats = []
                if payment.booking:
                    for booking_seat in payment.booking.booking_seats:
                        seats.append(f"{booking_seat.seat.row}{booking_seat.seat.column}")
                
                formatted_payments.append({
                    'id': payment.id,
                    'booking_id': payment.booking_id,
                    'customer_name': payment.booking.customer_name if payment.booking else 'N/A',
                    'movie_title': payment.booking.show.movie.title if payment.booking and payment.booking.show and payment.booking.show.movie else 'N/A',
                    'amount': float(payment.amount) if payment.amount else 0,
                    'payment_method': payment.get_payment_method_display(),
                    'status': payment.get_status_display(),
                    'status_badge_class': payment.get_status_badge_class(),
                    'payment_date': payment.created_at.strftime('%d %b %Y %H:%M') if payment.created_at else 'N/A',
                    'transaction_id': payment.reference_id,
                    'paypal_order_id': payment.paypal_order_id,
                    'seats': ', '.join(seats)
                })
            except Exception as e:
                ErrorLogger.log_error(e, request, context={'payment_id': payment.id})
                continue
        
        # Calculate summary statistics with validation
        try:
            summary = {
                'total_payments': len(formatted_payments),
                'completed_payments': len([p for p in formatted_payments if p['status'] == 'Completed']),
                'pending_payments': len([p for p in formatted_payments if p['status'] == 'Pending']),
                'failed_payments': len([p for p in formatted_payments if p['status'] == 'Failed']),
                'total_revenue': sum(p['amount'] for p in formatted_payments if p['status'] == 'Completed'),
                'monthly_revenue': 0
            }
            
            # Calculate monthly revenue with proper date validation
            current_month = datetime.now().month
            current_year = datetime.now().year
            monthly_revenue = 0
            
            for p in formatted_payments:
                if p['status'] == 'Completed' and p['payment_date'] != 'N/A':
                    try:
                        payment_date = datetime.strptime(p['payment_date'], '%d %b %Y %H:%M')
                        if payment_date.month == current_month and payment_date.year == current_year:
                            monthly_revenue += p['amount']
                    except ValueError:
                        continue
            
            summary['monthly_revenue'] = monthly_revenue
            
        except Exception as e:
            ErrorLogger.log_error(e, request, user_id=current_user.id)
            summary = {
                'total_payments': 0,
                'completed_payments': 0,
                'pending_payments': 0,
                'failed_payments': 0,
                'total_revenue': 0,
                'monthly_revenue': 0
            }
        
        return render_template('payments/index.html', 
                             title='Payments', 
                             payments=formatted_payments,
                             search_form=search_form,
                             summary=summary)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading payments', 'danger')
        return render_template('payments/index.html', 
                             title='Payments', 
                             payments=[],
                             search_form=PaymentSearchForm(),
                             summary={})

@bp.route('/process/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def process(booking_id):
    """Process payment for booking with enhanced validation"""
    try:
        # Validate booking ID
        if booking_id <= 0:
            flash('Invalid booking ID', 'danger')
            return redirect(url_for('bookings.index'))
        
        booking = Booking.query.get(booking_id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        # Validate booking status
        if booking.status not in ['confirmed', 'pending']:
            flash('This booking cannot be paid for', 'danger')
            return redirect(url_for('bookings.view', id=booking_id))
        
        # Validate booking amount
        if not booking.total_amount or float(booking.total_amount) <= 0:
            flash('Invalid booking amount', 'danger')
            return redirect(url_for('bookings.view', id=booking_id))
        
        # Check if payment already exists for this booking
        existing_payment = Payment.query.filter_by(booking_id=booking_id).first()
        if existing_payment and existing_payment.status != 'failed':
            flash('Payment has already been processed for this booking', 'warning')
            return redirect(url_for('payments.receipt', id=existing_payment.id))
        
        if request.method == 'POST':
            # Sanitize and validate payment method
            payment_method = InputSanitizer.sanitize_string(request.form.get('payment_method', ''), max_length=20)
            
            # Validate payment method
            valid_methods = ['cash', 'card', 'upi', 'netbanking', 'wallet', 'paypal']
            if payment_method not in valid_methods:
                flash('Invalid payment method', 'danger')
                return render_template('payments/process.html', 
                                     title='Process Payment', 
                                     booking=booking,
                                     paypal_client_id=get_paypal_service().get_client_id(),
                                     is_sandbox=get_paypal_service().is_sandbox())
            
            if payment_method == 'paypal':
                # PayPal is handled separately via JavaScript
                flash('Please use PayPal button to complete your payment', 'info')
                return render_template('payments/process.html', 
                                     title='Process Payment', 
                                     booking=booking,
                                     paypal_client_id=get_paypal_service().get_client_id(),
                                     is_sandbox=get_paypal_service().is_sandbox())
            
            # Process other payment methods
            return process_non_paypal_payment(booking, payment_method)
        
        return render_template('payments/process.html', 
                             title='Process Payment', 
                             booking=booking,
                             paypal_client_id=get_paypal_service().get_client_id(),
                             is_sandbox=get_paypal_service().is_sandbox())
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while processing payment', 'danger')
        return redirect(url_for('bookings.index'))

def process_non_paypal_payment(booking, payment_method):
    """Process non-PayPal payment methods with enhanced validation"""
    try:
        # Get and validate form data
        form_data = request.form
        notes = InputSanitizer.sanitize_string(form_data.get('notes', ''), max_length=500)
        
        # Validate booking amount
        if not booking.total_amount or float(booking.total_amount) <= 0:
            raise ValidationError("Invalid booking amount")
        
        # Create payment record
        payment = Payment(
            booking_id=booking.id,
            amount=booking.total_amount,
            mode=payment_method,
            notes=notes,
            created_by=current_user.id if current_user.is_authenticated else None,
            initiated_at=datetime.utcnow()
        )
        
        # Process payment-specific validation and fields
        if payment_method == 'cash':
            reference_id = InputSanitizer.sanitize_string(form_data.get('reference_id', ''), max_length=100)
            payment.reference_id = reference_id
            payment.mark_processing()
            
            # Simulate cash payment processing
            payment.mark_completed(reference_id=reference_id)
            
        elif payment_method == 'card':
            # Validate card payment data
            card_type = InputSanitizer.sanitize_string(form_data.get('card_type', ''), max_length=20)
            card_number = form_data.get('card_number', '').strip()
            expiry_month = form_data.get('expiry_month', '').strip()
            expiry_year = form_data.get('expiry_year', '').strip()
            reference_id = InputSanitizer.sanitize_string(form_data.get('reference_id', ''), max_length=100)
            
            # Validate card details
            if not DataValidators.validate_card_details(card_number, expiry_month, expiry_year):
                raise ValidationError("Invalid card details")
            
            if not DataValidators.validate_card_type(card_type):
                raise ValidationError("Invalid card type")
            
            payment.card_type = card_type
            payment.card_last_4 = card_number[-4:] if len(card_number) >= 4 else ''
            payment.card_expiry_month = expiry_month
            payment.card_expiry_year = expiry_year
            payment.card_authorization_code = reference_id
            payment.reference_id = reference_id
            
            payment.mark_processing()
            # Simulate card payment processing
            import time
            time.sleep(1)  # Simulate processing time
            payment.mark_completed(reference_id=reference_id)
            
        elif payment_method == 'upi':
            # Validate UPI payment data
            upi_id = form_data.get('upi_id', '').strip()
            transaction_id = InputSanitizer.sanitize_string(form_data.get('transaction_id', ''), max_length=100)
            reference_id = InputSanitizer.sanitize_string(form_data.get('reference_id', ''), max_length=100)
            
            if not DataValidators.validate_upi_id(upi_id):
                raise ValidationError("Invalid UPI ID format")
            
            payment.upi_id = upi_id
            payment.upi_transaction_id = transaction_id
            payment.utr_number = reference_id
            payment.reference_id = reference_id
            
            payment.mark_processing()
            # Simulate UPI processing
            payment.mark_completed(reference_id=reference_id)
            
        elif payment_method == 'netbanking':
            # Validate net banking payment data
            bank_name = InputSanitizer.sanitize_string(form_data.get('bank_name', ''), max_length=100)
            transaction_id = InputSanitizer.sanitize_string(form_data.get('transaction_id', ''), max_length=100)
            account_last_4 = form_data.get('account_last_4', '').strip()
            reference_id = InputSanitizer.sanitize_string(form_data.get('reference_id', ''), max_length=100)
            
            if not DataValidators.validate_account_number(account_last_4):
                raise ValidationError("Invalid account number format")
            
            payment.bank_name = bank_name
            payment.netbanking_transaction_id = transaction_id
            payment.account_last_4 = account_last_4
            payment.reference_id = reference_id
            
            payment.mark_processing()
            # Simulate net banking processing
            payment.mark_completed(reference_id=transaction_id)
            
        elif payment_method == 'wallet':
            # Validate wallet payment data
            wallet_type = InputSanitizer.sanitize_string(form_data.get('wallet_type', ''), max_length=50)
            mobile_number = form_data.get('mobile_number', '').strip()
            transaction_id = InputSanitizer.sanitize_string(form_data.get('transaction_id', ''), max_length=100)
            reference_id = InputSanitizer.sanitize_string(form_data.get('reference_id', ''), max_length=100)
            
            if not DataValidators.validate_phone_format(mobile_number):
                raise ValidationError("Invalid mobile number format")
            
            payment.wallet_type = wallet_type
            payment.wallet_mobile = mobile_number
            payment.wallet_transaction_id = transaction_id
            payment.reference_id = reference_id
            
            payment.mark_processing()
            # Simulate wallet processing
            payment.mark_completed(reference_id=transaction_id)
        
        else:
            raise ValidationError("Unsupported payment method")
        
        # Validate payment amount consistency
        if abs(float(payment.amount) - float(booking.total_amount)) > 0.01:
            ErrorLogger.log_security_event(
                'payment_amount_mismatch',
                f'Payment amount mismatch. Booking: {booking.total_amount}, Payment: {payment.amount}',
                request,
                user_id=current_user.id,
                context={'booking_id': booking.id, 'payment_method': payment_method},
                severity='high'
            )
            raise ValidationError("Payment amount mismatch")
        
        db.session.add(payment)
        
        # Update booking payment status
        booking.payment_method = payment_method
        booking.payment_date = datetime.utcnow()
        booking.status = 'confirmed'
        
        # Log payment operation
        PaymentAudit.log_operation(
            payment_id=payment.id,
            operation='CREATE',
            user_id=current_user.id if current_user.is_authenticated else None,
            new_values={
                'amount': float(payment.amount),
                'payment_method': payment.mode,
                'status': payment.status
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.commit()
        
        ErrorLogger.log_security_event(
            'payment_processed',
            f'User {current_user.username} processed payment {payment.id} for booking {booking.id}',
            request,
            user_id=current_user.id,
            context={
                'payment_id': payment.id,
                'booking_id': booking.id,
                'amount': float(payment.amount),
                'payment_method': payment_method
            }
        )
        
        flash('Payment processed successfully', 'success')
        return redirect(url_for('payments.receipt', id=payment.id))
        
    except ValidationError as e:
        db.session.rollback()
        ErrorLogger.log_security_event(
            'payment_validation_error',
            f'Validation error in payment processing: {str(e)}',
            request,
            user_id=current_user.id,
            context={'booking_id': booking.id, 'payment_method': payment_method},
            severity='medium'
        )
        flash(str(e), 'danger')
        return redirect(url_for('payments.process', booking_id=booking.id))
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing payment: {str(e)}")
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking.id})
        flash('An error occurred while processing payment', 'danger')
        return redirect(url_for('payments.process', booking_id=booking.id))

@bp.route('/create-paypal-order/<int:booking_id>', methods=['POST'])
@login_required
def create_paypal_order(booking_id):
    """Create a PayPal order for booking with enhanced validation"""
    try:
        # Validate booking ID
        if booking_id <= 0:
            return jsonify({'error': 'Invalid booking ID'}), 400
        
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Validate booking status and amount
        if booking.status not in ['confirmed', 'pending']:
            return jsonify({'error': 'Booking cannot be paid for'}), 400
        
        if not booking.total_amount or float(booking.total_amount) <= 0:
            return jsonify({'error': 'Invalid booking amount'}), 400
        
        # Check for existing payments
        existing_payment = Payment.query.filter_by(booking_id=booking_id).first()
        if existing_payment and existing_payment.status != 'failed':
            return jsonify({'error': 'Payment already exists for this booking'}), 400
        
        paypal_service = get_paypal_service()
        
        # Create PayPal order
        order = paypal_service.create_order(
            amount=float(booking.total_amount),
            description=f"Cinema Booking #{booking.id} - {booking.show.movie.title}"
        )
        
        if order:
            # Create pending payment record
            payment = Payment(
                booking_id=booking_id,
                amount=booking.total_amount,
                mode='paypal',
                paypal_order_id=order.id,
                status='pending',
                created_by=current_user.id if current_user.is_authenticated else None,
                initiated_at=datetime.utcnow()
            )
            
            db.session.add(payment)
            db.session.commit()
            
            # Store PayPal order ID in session for security
            session[f'paypal_order_{booking_id}'] = order.id
            
            ErrorLogger.log_security_event(
                'paypal_order_created',
                f'PayPal order {order.id} created for booking {booking_id}',
                request,
                user_id=current_user.id,
                context={
                    'booking_id': booking_id,
                    'paypal_order_id': order.id,
                    'amount': float(booking.total_amount)
                }
            )
            
            return jsonify({'orderID': order.id})
        else:
            return jsonify({'error': 'Failed to create PayPal order'}), 500
            
    except Exception as e:
        logger.error(f"Error creating PayPal order: {str(e)}")
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        return jsonify({'error': 'Failed to create PayPal order'}), 500

@bp.route('/capture-paypal-order/<int:booking_id>', methods=['POST'])
@login_required
def capture_paypal_order(booking_id):
    """Capture a PayPal order payment with enhanced validation"""
    try:
        # Validate booking ID
        if booking_id <= 0:
            return jsonify({'error': 'Invalid booking ID'}), 400
        
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Get and validate JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        paypal_order_id = InputSanitizer.sanitize_string(data.get('orderID', ''), max_length=100)
        
        if not paypal_order_id:
            return jsonify({'error': 'PayPal order ID is required'}), 400
        
        # Verify this order ID matches what we created (security check)
        session_order_id = session.get(f'paypal_order_{booking_id}')
        if session_order_id != paypal_order_id:
            ErrorLogger.log_security_event(
                'paypal_order_mismatch',
                f'PayPal order ID mismatch for booking {booking_id}',
                request,
                user_id=current_user.id,
                context={
                    'booking_id': booking_id,
                    'session_order_id': session_order_id,
                    'provided_order_id': paypal_order_id
                },
                severity='high'
            )
            return jsonify({'error': 'Invalid PayPal order ID'}), 400
        
        # Find pending payment record
        payment = Payment.query.filter_by(
            booking_id=booking_id,
            paypal_order_id=paypal_order_id,
            status='pending'
        ).first()
        
        if not payment:
            return jsonify({'error': 'Payment record not found'}), 404
        
        paypal_service = get_paypal_service()
        
        # Capture PayPal order
        capture_result = paypal_service.capture_order(paypal_order_id)
        
        if capture_result:
            # Validate capture amount
            if abs(float(capture_result.amount) - float(booking.total_amount)) > 0.01:
                ErrorLogger.log_security_event(
                    'paypal_capture_amount_mismatch',
                    f'PayPal capture amount mismatch for booking {booking_id}',
                    request,
                    user_id=current_user.id,
                    context={
                        'booking_id': booking_id,
                        'expected_amount': float(booking.total_amount),
                        'capture_amount': float(capture_result.amount)
                    },
                    severity='high'
                )
                return jsonify({'error': 'Payment amount mismatch'}), 400
            
            # Update payment record
            payment.paypal_capture_id = capture_result.id
            payment.paypal_payment_status = 'COMPLETED'
            payment.reference_id = capture_result.id
            payment.mark_completed()
            
            # Update booking payment status
            booking.payment_method = 'paypal'
            booking.payment_date = datetime.utcnow()
            booking.status = 'confirmed'
            
            # Clean up session
            session.pop(f'paypal_order_{booking_id}', None)
            
            db.session.commit()
            
            ErrorLogger.log_security_event(
                'paypal_payment_captured',
                f'PayPal payment {capture_result.id} captured for booking {booking_id}',
                request,
                user_id=current_user.id,
                context={
                    'booking_id': booking_id,
                    'paypal_capture_id': capture_result.id,
                    'amount': float(capture_result.amount)
                }
            )
            
            return jsonify({
                'success': True,
                'redirect_url': url_for('payments.receipt', id=payment.id)
            })
        else:
            payment.mark_failed('PayPal capture failed')
            db.session.commit()
            return jsonify({'error': 'Failed to capture PayPal payment'}), 500
            
    except Exception as e:
        logger.error(f"Error capturing PayPal order: {str(e)}")
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        return jsonify({'error': 'Failed to capture PayPal payment'}), 500

@bp.route('/receipt/<int:id>')
@login_required
def receipt(id):
    """View payment receipt with validation"""
    try:
        if id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Get seats for this booking
        seats = []
        if payment.booking:
            for booking_seat in payment.booking.booking_seats:
                seats.append(f"{booking_seat.seat.row}{booking_seat.seat.column}")
            
            # Add seats to booking object
            payment.booking.seats = ', '.join(seats)
        
        return render_template('payments/receipt.html', title='Payment Receipt', payment=payment)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading receipt', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/receipt/<int:id>/pdf')
@login_required
def receipt_pdf(id):
    """Generate PDF receipt with validation"""
    try:
        if id <= 0:
            return jsonify({'error': 'Invalid payment ID'}), 400
        
        payment = Payment.query.get(id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Get seats for this booking
        seats = []
        if payment.booking:
            for booking_seat in payment.booking.booking_seats:
                seats.append(f"{booking_seat.seat.row}{booking_seat.seat.column}")
        
        # Prepare and sanitize payment data for PDF generation
        payment_data = {
            'id': payment.id,
            'customer_name': InputSanitizer.sanitize_string(payment.booking.customer_name, max_length=100) if payment.booking else 'N/A',
            'contact_number': InputSanitizer.sanitize_string(payment.booking.contact_number, max_length=20) if payment.booking else 'N/A',
            'email': InputSanitizer.sanitize_email(payment.booking.email) if payment.booking else 'N/A',
            'booking_id': payment.booking_id,
            'movie_title': InputSanitizer.sanitize_string(payment.booking.show.movie.title, max_length=200) if payment.booking and payment.booking.show and payment.booking.show.movie else 'N/A',
            'screen_name': InputSanitizer.sanitize_string(payment.booking.show.screen.name, max_length=100) if payment.booking and payment.booking.show and payment.booking.show.screen else 'N/A',
            'show_date': payment.booking.show.show_date.strftime('%d %b %Y') if payment.booking and payment.booking.show and payment.booking.show.show_date else 'N/A',
            'show_time': payment.booking.show.show_time.strftime('%H:%M') if payment.booking and payment.booking.show and payment.booking.show.show_time else 'N/A',
            'seats': ', '.join(seats),
            'amount': float(payment.amount) if payment.amount else 0,
            'payment_method': payment.get_payment_method_display(),
            'transaction_id': InputSanitizer.sanitize_string(payment.reference_id, max_length=100),
            'paypal_order_id': InputSanitizer.sanitize_string(payment.paypal_order_id, max_length=100),
            'payment_date': payment.payment_date,
            'notes': InputSanitizer.sanitize_string(payment.notes, max_length=500) if payment.notes else '',
            'status': payment.get_status_display()
        }
        
        # Generate PDF
        pdf_data = generate_receipt_pdf(payment_data)
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=receipt_{payment.id}.pdf'
        
        return response
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': id})
        ErrorHandler.handle_error(e, request)
        return jsonify({'error': 'Failed to generate PDF receipt'}), 500

@bp.route('/refund/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def refund(payment_id):
    """Process payment refund with enhanced validation"""
    try:
        if payment_id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        if not payment.can_be_refunded():
            flash('This payment cannot be refunded', 'danger')
            return redirect(url_for('payments.receipt', id=payment.id))
        
        form = RefundPaymentForm(original_amount=float(payment.amount))
        
        if form.validate_on_submit():
            try:
                # Sanitize and validate form data
                refund_amount = float(form.refund_amount.data)
                refund_reason = InputSanitizer.sanitize_string(form.refund_reason.data, max_length=500)
                refund_method = InputSanitizer.sanitize_string(form.refund_method.data, max_length=20)
                reference_id = InputSanitizer.sanitize_string(form.reference_id.data, max_length=100)
                refund_notes = InputSanitizer.sanitize_string(form.refund_notes.data, max_length=500)
                
                # Validate refund amount
                if refund_amount <= 0:
                    raise ValidationError("Refund amount must be positive")
                
                if refund_amount > float(payment.amount):
                    raise ValidationError("Refund amount cannot exceed payment amount")
                
                # Validate refund method
                valid_refund_methods = ['cash', 'card', 'upi', 'netbanking', 'wallet', 'bank_transfer']
                if refund_method not in valid_refund_methods:
                    raise ValidationError("Invalid refund method")
                
                # Create refund record
                refund_record = PaymentRefund(
                    payment_id=payment.id,
                    refund_amount=refund_amount,
                    refund_reason=refund_reason,
                    refund_method=refund_method,
                    refund_reference_id=reference_id,
                    refund_notes=refund_notes,
                    processed_by=current_user.id if current_user.is_authenticated else None
                )
                
                db.session.add(refund_record)
                
                # Update payment status
                payment.mark_refunded(
                    refund_amount=refund_amount,
                    refund_reason=refund_reason,
                    refund_method=refund_method,
                    refund_reference_id=reference_id
                )
                
                # Update booking status if fully refunded
                if refund_amount >= float(payment.amount):
                    payment.booking.status = 'cancelled'
                
                # Log refund operation
                PaymentAudit.log_operation(
                    payment_id=payment.id,
                    operation='REFUND',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    new_values={
                        'refund_amount': refund_amount,
                        'refund_reason': refund_reason,
                        'refund_method': refund_method
                    },
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                
                db.session.commit()
                
                ErrorLogger.log_security_event(
                    'payment_refunded',
                    f'User {current_user.username} refunded {refund_amount} for payment {payment.id}',
                    request,
                    user_id=current_user.id,
                    context={
                        'payment_id': payment.id,
                        'refund_amount': refund_amount,
                        'refund_method': refund_method
                    }
                )
                
                flash('Refund processed successfully', 'success')
                return redirect(url_for('payments.receipt', id=payment.id))
                
            except ValidationError as e:
                db.session.rollback()
                ErrorLogger.log_security_event(
                    'refund_validation_error',
                    f'Validation error in refund processing: {str(e)}',
                    request,
                    user_id=current_user.id,
                    context={'payment_id': payment_id},
                    severity='medium'
                )
                flash(str(e), 'danger')
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error processing refund: {str(e)}")
                ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
                flash('An error occurred while processing refund', 'danger')
        
        return render_template('payments/refund.html', title='Process Refund', payment=payment, form=form)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading refund page', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/status/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def update_status(payment_id):
    """Update payment status with validation and audit logging"""
    try:
        if payment_id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        form = PaymentStatusForm()
        
        if form.validate_on_submit():
            try:
                # Sanitize and validate form data
                new_status = InputSanitizer.sanitize_string(form.status.data, max_length=20)
                notes = InputSanitizer.sanitize_string(form.notes.data, max_length=500)
                
                # Validate status
                valid_statuses = ['pending', 'processing', 'completed', 'failed', 'refunded']
                if new_status not in valid_statuses:
                    raise ValidationError("Invalid payment status")
                
                old_status = payment.status
                
                # Update payment status
                payment.status = new_status
                payment.notes = notes
                payment.updated_at = datetime.utcnow()
                
                # Add status change to history
                payment._add_status_history(new_status, notes)
                
                # Log status update
                PaymentAudit.log_operation(
                    payment_id=payment.id,
                    operation='UPDATE_STATUS',
                    user_id=current_user.id if current_user.is_authenticated else None,
                    old_values={'status': old_status},
                    new_values={'status': new_status},
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                
                db.session.commit()
                
                ErrorLogger.log_security_event(
                    'payment_status_updated',
                    f'User {current_user.username} updated payment {payment.id} status from {old_status} to {new_status}',
                    request,
                    user_id=current_user.id,
                    context={
                        'payment_id': payment.id,
                        'old_status': old_status,
                        'new_status': new_status
                    }
                )
                
                flash('Payment status updated successfully', 'success')
                return redirect(url_for('payments.receipt', id=payment.id))
                
            except ValidationError as e:
                db.session.rollback()
                ErrorLogger.log_security_event(
                    'status_update_validation_error',
                    f'Validation error in status update: {str(e)}',
                    request,
                    user_id=current_user.id,
                    context={'payment_id': payment_id},
                    severity='medium'
                )
                flash(str(e), 'danger')
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating payment status: {str(e)}")
                ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
                flash('An error occurred while updating payment status', 'danger')
        
        # Pre-select current status
        form.status.data = payment.status
        form.notes.data = payment.notes
        
        return render_template('payments/update_status.html', title='Update Payment Status', payment=payment, form=form)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading status update page', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/history/<int:payment_id>')
@login_required
def status_history(payment_id):
    """View payment status history with validation"""
    try:
        if payment_id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Get status history
        history = PaymentStatusHistory.query.filter_by(payment_id=payment_id).order_by(PaymentStatusHistory.changed_at.desc()).all()
        
        return render_template('payments/status_history.html', title='Payment History', payment=payment, history=history)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading payment history', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/audit/<int:payment_id>')
@login_required
def audit_trail(payment_id):
    """View payment audit trail with validation"""
    try:
        if payment_id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Get audit trail
        audit_trail = PaymentAudit.query.filter_by(payment_id=payment_id).order_by(PaymentAudit.timestamp.desc()).all()
        
        # Parse JSON values for display
        for audit in audit_trail:
            if audit.old_values:
                try:
                    audit.old_values_dict = json.loads(audit.old_values)
                except:
                    audit.old_values_dict = {}
            else:
                audit.old_values_dict = {}
                
            if audit.new_values:
                try:
                    audit.new_values_dict = json.loads(audit.new_values)
                except:
                    audit.new_values_dict = {}
            else:
                audit.new_values_dict = {}
        
        return render_template('payments/audit_trail.html', title='Payment Audit Trail', payment=payment, audit_trail=audit_trail)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading audit trail', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/email-receipt/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def email_receipt(payment_id):
    """Send payment receipt via email with validation"""
    try:
        if payment_id <= 0:
            flash('Invalid payment ID', 'danger')
            return redirect(url_for('payments.index'))
        
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        form = EmailReceiptForm()
        
        if form.validate_on_submit():
            try:
                # Sanitize and validate email
                recipient_email = InputSanitizer.sanitize_email(form.email.data)
                message = InputSanitizer.sanitize_string(form.message.data, max_length=500) if form.message.data else ""
                
                if not DataValidators.validate_email_format(recipient_email):
                    raise ValidationError("Invalid email format")
                
                # Send email receipt
                success = send_receipt_email(
                    payment=payment,
                    recipient_email=recipient_email,
                    message=message
                )
                
                if success:
                    flash(f'Receipt sent successfully to {recipient_email}', 'success')
                else:
                    flash('Failed to send receipt. Please try again.', 'danger')
                    
                return redirect(url_for('payments.receipt', id=payment.id))
                
            except ValidationError as e:
                ErrorLogger.log_security_event(
                    'email_validation_error',
                    f'Validation error in email receipt: {str(e)}',
                    request,
                    user_id=current_user.id,
                    context={'payment_id': payment_id},
                    severity='medium'
                )
                flash(str(e), 'danger')
                
            except Exception as e:
                logger.error(f"Error sending email receipt: {str(e)}")
                ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
                flash('An error occurred while sending receipt', 'danger')
        
        # Pre-fill email if booking has email
        if payment.booking and payment.booking.email and not form.email.data:
            form.email.data = payment.booking.email
        
        return render_template('payments/email_receipt_form.html',
                             title='Email Receipt',
                             payment=payment,
                             form=form)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        ErrorHandler.handle_error(e, request)
        flash('An error occurred while loading email receipt form', 'danger')
        return redirect(url_for('payments.index'))