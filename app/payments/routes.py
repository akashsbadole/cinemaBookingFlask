"""
Payment Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, abort, make_response
from flask_login import login_required, current_user
from app.payments import bp
from app.payments.forms import (
    PaymentForm, RefundPaymentForm, EmailReceiptForm, PaymentMethodForm,
    CashPaymentForm, CardPaymentForm, UpiPaymentForm, NetBankingPaymentForm, 
    WalletPaymentForm, PaymentStatusForm, PaymentSearchForm
)
from app.payments.models import Payment, PaymentRefund, PaymentStatusHistory, PaymentAudit
from app.bookings.models import Booking
from app.movies.models import Movie
from app.shows.models import Show
from app.error_handlers import ErrorLogger
from app.database import db
from app.validators import InputSanitizer, SecurityValidator, DataValidators
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

@bp.route('/process/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def process_payment(booking_id):
    """Process payment for a booking"""
    try:
        # Validate booking
        booking = Booking.query.get(booking_id)
        if not booking:
            flash('Booking not found', 'danger')
            return redirect(url_for('bookings.index'))
        
        # Check if payment already exists
        existing_payment = Payment.query.filter_by(booking_id=booking_id).first()
        if existing_payment:
            flash('Payment already processed for this booking', 'warning')
            return redirect(url_for('payments.receipt', id=existing_payment.id))
        
        # Initialize forms
        payment_method_form = PaymentMethodForm()
        cash_form = CashPaymentForm()
        card_form = CardPaymentForm()
        upi_form = UpiPaymentForm()
        netbanking_form = NetBankingPaymentForm()
        wallet_form = WalletPaymentForm()
        
        if request.method == 'POST':
            payment_method = request.form.get('payment_method')
            amount_received = float(request.form.get('amount_received', 0))
            
            # Validate amount
            if amount_received <= 0:
                flash('Invalid payment amount', 'danger')
                return render_template('payments/process.html', 
                                    booking=booking, 
                                    payment_method_form=payment_method_form,
                                    cash_form=cash_form,
                                    card_form=card_form,
                                    upi_form=upi_form,
                                    netbanking_form=netbanking_form,
                                    wallet_form=wallet_form,
                                    now_year=datetime.now().year)
            
            # Create payment record
            payment = Payment(
                booking_id=booking_id,
                amount=amount_received,
                mode=payment_method,
                status='pending',
                created_by=current_user.id,
                notes=request.form.get('notes', '')
            )
            
            # Process based on payment method
            if payment_method == 'cash':
                cash_form = CashPaymentForm(request.form)
                if cash_form.validate():
                    payment.mode = 'cash'
                    payment.reference_id = cash_form.reference_id.data
                    payment.mark_completed()
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Log audit
                    PaymentAudit.log_operation(
                        payment.id, 'CREATE', current_user.id,
                        new_values={'mode': 'cash', 'amount': amount_received, 'status': 'completed'},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    
                    flash('Cash payment processed successfully!', 'success')
                    return redirect(url_for('payments.receipt', id=payment.id))
                else:
                    flash('Please correct errors in form', 'danger')
                    return render_template('payments/process.html', 
                                        booking=booking, 
                                        payment_method_form=payment_method_form,
                                        cash_form=cash_form,
                                        card_form=card_form,
                                        upi_form=upi_form,
                                        netbanking_form=netbanking_form,
                                        wallet_form=wallet_form,
                                        now_year=datetime.now().year)
            
            elif payment_method == 'card':
                card_form = CardPaymentForm(request.form)
                if card_form.validate():
                    payment.mode = 'card'
                    payment.card_type = card_form.card_type.data
                    payment.card_last_4 = card_form.card_number.data[-4:]
                    payment.card_expiry_month = card_form.expiry_month.data
                    payment.card_expiry_year = card_form.expiry_year.data
                    payment.card_authorization_code = card_form.reference_id.data
                    payment.mark_completed()
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Log audit
                    PaymentAudit.log_operation(
                        payment.id, 'CREATE', current_user.id,
                        new_values={'mode': 'card', 'amount': amount_received, 'status': 'completed'},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    
                    flash('Card payment processed successfully!', 'success')
                    return redirect(url_for('payments.receipt', id=payment.id))
                else:
                    flash('Please correct errors in form', 'danger')
                    return render_template('payments/process.html', 
                                        booking=booking, 
                                        payment_method_form=payment_method_form,
                                        cash_form=cash_form,
                                        card_form=card_form,
                                        upi_form=upi_form,
                                        netbanking_form=netbanking_form,
                                        wallet_form=wallet_form,
                                        now_year=datetime.now().year)
            
            elif payment_method == 'upi':
                upi_form = UpiPaymentForm(request.form)
                if upi_form.validate():
                    payment.mode = 'upi'
                    payment.upi_id = upi_form.upi_id.data
                    payment.upi_transaction_id = upi_form.transaction_id.data
                    payment.utr_number = upi_form.reference_id.data
                    payment.mark_completed()
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Log audit
                    PaymentAudit.log_operation(
                        payment.id, 'CREATE', current_user.id,
                        new_values={'mode': 'upi', 'amount': amount_received, 'status': 'completed'},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    
                    flash('UPI payment processed successfully!', 'success')
                    return redirect(url_for('payments.receipt', id=payment.id))
                else:
                    flash('Please correct errors in form', 'danger')
                    return render_template('payments/process.html', 
                                        booking=booking, 
                                        payment_method_form=payment_method_form,
                                        cash_form=cash_form,
                                        card_form=card_form,
                                        upi_form=upi_form,
                                        netbanking_form=netbanking_form,
                                        wallet_form=wallet_form,
                                        now_year=datetime.now().year)
            
            elif payment_method == 'netbanking':
                netbanking_form = NetBankingPaymentForm(request.form)
                if netbanking_form.validate():
                    payment.mode = 'netbanking'
                    payment.bank_name = netbanking_form.bank_name.data
                    payment.netbanking_transaction_id = netbanking_form.transaction_id.data
                    payment.account_last_4 = netbanking_form.account_last_4.data
                    payment.reference_id = netbanking_form.reference_id.data
                    payment.mark_completed()
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Log audit
                    PaymentAudit.log_operation(
                        payment.id, 'CREATE', current_user.id,
                        new_values={'mode': 'netbanking', 'amount': amount_received, 'status': 'completed'},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    
                    flash('Net Banking payment processed successfully!', 'success')
                    return redirect(url_for('payments.receipt', id=payment.id))
                else:
                    flash('Please correct errors in form', 'danger')
                    return render_template('payments/process.html', 
                                        booking=booking, 
                                        payment_method_form=payment_method_form,
                                        cash_form=cash_form,
                                        card_form=card_form,
                                        upi_form=upi_form,
                                        netbanking_form=netbanking_form,
                                        wallet_form=wallet_form,
                                        now_year=datetime.now().year)
            
            elif payment_method == 'wallet':
                wallet_form = WalletPaymentForm(request.form)
                if wallet_form.validate():
                    payment.mode = 'wallet'
                    payment.wallet_type = wallet_form.wallet_type.data
                    payment.wallet_mobile = wallet_form.mobile_number.data
                    payment.wallet_transaction_id = wallet_form.transaction_id.data
                    payment.reference_id = wallet_form.reference_id.data
                    payment.mark_completed()
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Log audit
                    PaymentAudit.log_operation(
                        payment.id, 'CREATE', current_user.id,
                        new_values={'mode': 'wallet', 'amount': amount_received, 'status': 'completed'},
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    
                    flash('Wallet payment processed successfully!', 'success')
                    return redirect(url_for('payments.receipt', id=payment.id))
                else:
                    flash('Please correct errors in form', 'danger')
                    return render_template('payments/process.html', 
                                        booking=booking, 
                                        payment_method_form=payment_method_form,
                                        cash_form=cash_form,
                                        card_form=card_form,
                                        upi_form=upi_form,
                                        netbanking_form=netbanking_form,
                                        wallet_form=wallet_form,
                                        now_year=datetime.now().year)
            
            elif payment_method == 'paypal':
                payment.mode = 'paypal'
                payment.mark_processing()
                db.session.add(payment)
                db.session.commit()
                
                # Log audit
                PaymentAudit.log_operation(
                    payment.id, 'CREATE', current_user.id,
                    new_values={'mode': 'paypal', 'amount': amount_received, 'status': 'processing'},
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent')
                )
                
                flash('Redirecting to PayPal for payment...', 'info')
                return redirect(url_for('payments.create_paypal_order', booking_id=booking_id))
            
            else:
                flash('Invalid payment method', 'danger')
                return render_template('payments/process.html', 
                                    booking=booking, 
                                    payment_method_form=payment_method_form,
                                    cash_form=cash_form,
                                    card_form=card_form,
                                    upi_form=upi_form,
                                    netbanking_form=netbanking_form,
                                    wallet_form=wallet_form,
                                    now_year=datetime.now().year)
        
        # GET request - show payment form
        return render_template('payments/process.html', 
                            booking=booking, 
                            payment_method_form=payment_method_form,
                            cash_form=cash_form,
                            card_form=card_form,
                            upi_form=upi_form,
                            netbanking_form=netbanking_form,
                            wallet_form=wallet_form,
                            now_year=datetime.now().year)
            
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        logger.error(f"Error processing payment: {str(e)}")
        flash('An error occurred while processing payment', 'danger')
        return redirect(url_for('bookings.view', id=booking_id))

@bp.route('/create_paypal_order/<int:booking_id>', methods=['POST'])
@login_required
def create_paypal_order(booking_id):
    """Create PayPal order for payment"""
    try:
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Get pending PayPal payment
        payment = Payment.query.filter_by(
            booking_id=booking_id, 
            mode='paypal', 
            status='processing'
        ).first()
        
        if not payment:
            return jsonify({'error': 'PayPal payment not found or not in processing state'}), 404
        
        # Import PayPal service
        from app.paypal_service import PayPalService
        paypal_service = PayPalService()
        
        # Create PayPal order
        order_data = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'reference_id': str(booking_id),
                'description': f'Cinema Booking #{booking_id}',
                'amount': {
                    'currency_code': 'USD',
                    'value': str(float(payment.amount))
                }
            }]
        }
        
        response = paypal_service.create_order(order_data)
        
        if response.get('error'):
            payment.mark_failed(response.get('error'))
            db.session.commit()
            return jsonify({'error': 'Failed to create PayPal order'}), 500
        
        # Update payment with PayPal order ID
        payment.paypal_order_id = response.get('id')
        db.session.commit()
        
        return jsonify({
            'orderID': response.get('id'),
            'approval_url': next((link['href'] for link in response.get('links', []) 
                               if link.get('rel') == 'approve'), None)
        })
        
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        return jsonify({'error': 'Failed to create PayPal order'}), 500

@bp.route('/capture_paypal_order/<int:booking_id>', methods=['POST'])
@login_required
def capture_paypal_order(booking_id):
    """Capture PayPal order after approval"""
    try:
        data = request.get_json()
        order_id = data.get('orderID')
        
        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400
        
        # Get payment record
        payment = Payment.query.filter_by(
            booking_id=booking_id, 
            paypal_order_id=order_id,
            status='processing'
        ).first()
        
        if not payment:
            return jsonify({'error': 'PayPal order not found'}), 404
        
        # Import PayPal service
        from app.paypal_service import PayPalService
        paypal_service = PayPalService()
        
        # Capture the order
        response = paypal_service.capture_order(order_id)
        
        if response.get('error'):
            payment.mark_failed(response.get('error'))
            db.session.commit()
            return jsonify({'error': 'Failed to capture PayPal payment'}), 500
        
        # Update payment with capture details
        payment.paypal_capture_id = response.get('id')
        payment.paypal_payment_status = 'COMPLETED'
        payment.mark_completed()
        db.session.commit()
        
        # Log audit
        PaymentAudit.log_operation(
            payment.id, 'UPDATE', current_user.id,
            new_values={'status': 'completed', 'paypal_capture_id': response.get('id')},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('payments.receipt', id=payment.id)
        })
        
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'booking_id': booking_id})
        return jsonify({'error': 'Failed to capture PayPal payment'}), 500

@bp.route('/capture/<int:payment_id>', methods=['POST'])
@login_required
def capture_payment(payment_id):
    """Capture payment (for PayPal and other delayed payment methods)"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            ErrorLogger.log_error(f"Payment not found: {payment_id}", request, context={'payment_id': payment_id})
            return jsonify({'error': 'Payment not found'}), 404
        
        if payment.status != 'pending':
            return jsonify({'error': 'Payment is not in pending status'}), 400
        
        # Here you would integrate with payment gateway to capture payment
        # For now, simulate successful capture
        payment.status = 'completed'
        payment.reference_id = f'CAPTURED_{payment_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
        payment.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update booking status
        booking = payment.booking
        booking.status = 'confirmed'
        db.session.commit()
        
        # Log audit
        PaymentAudit.log_operation(
            payment.id, 'UPDATE', current_user.id,
            new_values={'status': 'completed', 'reference_id': payment.reference_id},
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        flash('Payment captured successfully!', 'success')
        return jsonify({'success': True, 'message': 'Payment captured successfully'})
        
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        return jsonify({'success': False, 'error': 'Failed to capture payment'}), 500

@bp.route('/refund/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def refund_payment(payment_id):
    """Process refund for a payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        if not payment.can_be_refunded():
            flash('This payment cannot be refunded', 'warning')
            return redirect(url_for('payments.view', id=payment_id))
        
        form = RefundPaymentForm(original_amount=payment.amount)
        
        if form.validate_on_submit():
            # Create refund record
            refund = PaymentRefund(
                payment_id=payment_id,
                refund_amount=form.refund_amount.data,
                refund_reason=form.refund_reason.data,
                refund_method=form.refund_method.data,
                refund_reference_id=request.form.get('reference_id'),
                refund_notes=form.refund_notes.data,
                processed_by=current_user.id
            )
            
            db.session.add(refund)
            
            # Update payment status
            payment.mark_refunded(
                refund_amount=form.refund_amount.data,
                refund_reason=form.refund_reason.data,
                refund_method=form.refund_method.data,
                refund_reference_id=request.form.get('reference_id')
            )
            
            db.session.commit()
            
            # Log audit
            PaymentAudit.log_operation(
                payment.id, 'REFUND', current_user.id,
                new_values={
                    'status': 'refunded',
                    'refund_amount': float(form.refund_amount.data),
                    'refund_reason': form.refund_reason.data
                },
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            flash('Refund processed successfully!', 'success')
            return redirect(url_for('payments.view', id=payment_id))
        
        return render_template('payments/refund.html', payment=payment, form=form)
        
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error processing refund: {str(e)}")
        flash('An error occurred while processing refund', 'danger')
        return redirect(url_for('payments.view', id=payment_id))

@bp.route('/email_receipt/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def email_receipt(payment_id):
    """Send email receipt for a payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        form = EmailReceiptForm()
        
        if form.validate_on_submit():
            # Get booking details
            booking = payment.booking
            show = booking.show
            movie = show.movie
            
            # Prepare receipt data
            receipt_data = {
                'payment_id': payment.id,
                'booking_id': booking.id,
                'movie_title': movie.title,
                'show_time': show.show_time.strftime('%Y-%m-%d %H:%M'),
                'screen_name': show.screen.name,
                'seats': booking.seats,
                'total_amount': float(payment.amount),
                'payment_method': payment.get_payment_method_display(),
                'reference_id': payment.reference_id,
                'payment_date': payment.created_at.strftime('%Y-%m-%d %H:%M')
            }
            
            # TODO: Implement email sending functionality
            # For now, just show success message
            flash('Email receipt functionality will be available soon!', 'info')
            return redirect(url_for('payments.view', id=payment_id))
        
        return render_template('payments/email_receipt_form.html', payment=payment, form=form)
        
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error sending email receipt: {str(e)}")
        flash('An error occurred while sending receipt', 'danger')
        return redirect(url_for('payments.view', id=payment_id))

@bp.route('/update_status/<int:payment_id>', methods=['GET', 'POST'])
@login_required
def update_status(payment_id):
    """Update payment status"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        form = PaymentStatusForm()
        
        if form.validate_on_submit():
            old_status = payment.status
            new_status = form.status.data
            notes = form.notes.data
            
            # Update status
            payment.status = new_status
            payment.updated_by = current_user.id
            payment.updated_at = datetime.utcnow()
            
            # Update timestamps based on status
            if new_status == 'completed':
                payment.completed_at = datetime.utcnow()
            elif new_status == 'refunded':
                payment.refunded_at = datetime.utcnow()
            elif new_status == 'failed':
                payment.failed_at = datetime.utcnow()
            
            # Add to status history
            payment._add_status_history(new_status, notes)
            
            db.session.commit()
            
            # Log audit
            PaymentAudit.log_operation(
                payment.id, 'UPDATE', current_user.id,
                old_values={'status': old_status},
                new_values={'status': new_status, 'notes': notes},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            flash('Payment status updated successfully!', 'success')
            return redirect(url_for('payments.view', id=payment_id))
        
        # Pre-fill form with current status
        form.status.data = payment.status
        return render_template('payments/update_status.html', payment=payment, form=form)
        
    except Exception as e:
        db.session.rollback()
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error updating payment status: {str(e)}")
        flash('An error occurred while updating payment status', 'danger')
        return redirect(url_for('payments.view', id=payment_id))

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    """Payment management dashboard"""
    try:
        # Get search parameters
        search_form = PaymentSearchForm()
        
        # Sanitize search parameters
        search_term = InputSanitizer.sanitize_string(request.args.get('search_term', ''), max_length=100)
        search_type = InputSanitizer.sanitize_string(request.args.get('search_type', 'all'), max_length=20)
        status_filter = InputSanitizer.sanitize_string(request.args.get('status_filter', 'all'), max_length=20)
        payment_method_filter = InputSanitizer.sanitize_string(request.args.get('payment_method_filter', 'all'), max_length=20)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Security check for injection attempts
        if SecurityValidator.detect_sql_injection([search_term, search_type, status_filter, payment_method_filter]):
            ErrorLogger.log_security_event(
                'sql_injection_attempt',
                f'SQL injection attempt detected in payment search',
                request,
                user_id=current_user.id,
                severity='high'
            )
            abort(400, "Invalid input detected")
        
        # Start with base query
        query = Payment.query
        
        # Apply search filters
        if search_term:
            if search_type == 'all' or search_type == 'transaction_id':
                query = query.filter(Payment.reference_id.ilike(f'%{search_term}%'))
            elif search_type == 'booking_id':
                try:
                    booking_id = int(search_term)
                    query = query.filter(Payment.booking_id == booking_id)
                except ValueError:
                    flash('Invalid booking ID format', 'warning')
            elif search_type == 'customer':
                query = query.join(Booking).filter(Booking.customer_name.ilike(f'%{search_term}%'))
        
        # Apply status filter
        if status_filter != 'all':
            query = query.filter(Payment.status == status_filter)
        
        # Apply payment method filter
        if payment_method_filter != 'all':
            query = query.filter(Payment.mode == payment_method_filter)
        
        # Apply date filters
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(Payment.created_at >= from_date)
            except ValueError:
                flash('Invalid start date format', 'warning')
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(Payment.created_at <= to_date)
            except ValueError:
                flash('Invalid end date format', 'warning')
        
        # Get filtered payments with booking information
        payments = query.join(Booking).join(Show).join(Movie).order_by(Payment.created_at.desc()).limit(100).all()
        
        # Format payment data for template
        formatted_payments = []
        for payment in payments:
            try:
                formatted_payments.append({
                    'id': payment.id,
                    'booking_id': payment.booking_id,
                    'customer_name': payment.booking.customer_name if payment.booking else 'N/A',
                    'movie_title': payment.booking.show.movie.title if payment.booking and payment.booking.show and payment.booking.show.movie else 'N/A',
                    'amount': float(payment.amount) if payment.amount else 0,
                    'mode': payment.mode,
                    'payment_method': payment.get_payment_method_display(),
                    'status': payment.status,
                    'get_status_badge_class': payment.get_status_badge_class(),
                    'payment_date': payment.created_at.strftime('%d %b %Y %H:%M') if payment.created_at else 'N/A',
                    'seats': payment.booking.seats if payment.booking and payment.booking.seats else 'N/A'
                })
            except Exception as e:
                ErrorLogger.log_error(e, request, context={'payment_id': payment.id})
                continue
        
        # Calculate summary statistics
        summary = {
            'total_payments': len(formatted_payments),
            'completed_payments': len([p for p in formatted_payments if p['status'] == 'completed']),
            'pending_payments': len([p for p in formatted_payments if p['status'] == 'pending']),
            'failed_payments': len([p for p in formatted_payments if p['status'] == 'failed']),
            'total_revenue': sum([p['amount'] for p in formatted_payments if p['status'] == 'completed'])
        }
        
        return render_template('payments/index.html', 
                            title='Payments', 
                            payments=formatted_payments,
                            summary=summary,
                            search_form=search_form)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        logger.error(f"Error loading payments index: {str(e)}")
        flash('An error occurred while loading payments', 'danger')
        return render_template('payments/index.html', 
                            title='Payments', 
                            payments=[],
                            summary={},
                            search_form=PaymentSearchForm())

@bp.route('/view/<int:payment_id>')
@login_required
def view(payment_id):
    """View payment details"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        return render_template('payments/view.html', title=f'Payment #{payment_id}', payment=payment)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error viewing payment: {str(e)}")
        flash('An error occurred while loading payment details', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    """View payment receipt"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        return render_template('payments/receipt.html', title='Payment Receipt', payment=payment)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error viewing receipt: {str(e)}")
        flash('An error occurred while loading receipt', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/status_history/<int:payment_id>')
@login_required
def status_history(payment_id):
    """Get payment status history"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Get status history
        history = PaymentStatusHistory.query.filter_by(payment_id=payment_id).order_by(PaymentStatusHistory.changed_at.desc()).all()
        
        return render_template('payments/status_history.html', 
                            title='Payment Status History', 
                            payment=payment, 
                            history=history)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error loading status history: {str(e)}")
        flash('An error occurred while loading status history', 'danger')
        return redirect(url_for('payments.view', id=payment_id))

@bp.route('/audit_trail')
@login_required
def audit_trail():
    """Payment audit trail"""
    try:
        # Get all payments with their audit information
        payments = db.session.query(
            Payment,
            Payment.created_at.label('created_at_formatted'),
            Payment.completed_at.label('completed_at_formatted')
        ).order_by(Payment.created_at.desc()).limit(100).all()
        
        # Get audit trail for all payments
        audit_trail = []
        for payment in payments:
            payment_audits = db.session.query(PaymentAudit).filter_by(payment_id=payment.id).order_by(PaymentAudit.timestamp.desc()).all()
            for audit in payment_audits:
                # Parse JSON values for template
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
                
                audit_trail.append(audit)
        
        return render_template('payments/audit_trail.html', title='Payment Audit Trail', payments=payments, audit_trail=audit_trail)
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id)
        logger.error(f"Error loading audit trail: {str(e)}")
        flash('An error occurred while loading audit trail', 'danger')
        return redirect(url_for('payments.index'))

@bp.route('/audit_trail/<int:payment_id>')
@login_required
def payment_audit_trail(payment_id):
    """Payment audit trail for a specific payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Get audit trail for this payment
        audit_trail = db.session.query(PaymentAudit).filter_by(payment_id=payment_id).order_by(PaymentAudit.timestamp.desc()).all()
        
        # Parse JSON values for template
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
        logger.error(f"Error loading audit trail: {str(e)}")
        flash('An error occurred while loading audit trail', 'danger')
        return redirect(url_for('payments.view', id=payment_id))

@bp.route('/receipt/<int:payment_id>/pdf')
@login_required
def receipt_pdf(payment_id):
    """Generate PDF receipt for a payment"""
    try:
        payment = Payment.query.get(payment_id)
        if not payment:
            flash('Payment not found', 'danger')
            return redirect(url_for('payments.index'))
        
        # Prepare receipt data for PDF generation
        receipt_data = {
            'receipt_id': f"RCP-{payment_id}-{payment.created_at.strftime('%Y%m%d') if payment.created_at else 'N/A'}",
            'payment_date': payment.created_at.strftime('%d %b %Y %H:%M') if payment.created_at else 'N/A',
            'payment_method': payment.get_payment_method_display(),
            'payment_method_details': {},
            'transaction_id': payment.reference_id or 'N/A',
            'status': payment.get_status_display(),
            'status_badge_class': payment.get_status_badge_class(),
            'customer_name': payment.booking.customer_name if payment.booking else 'N/A',
            'customer_contact': payment.booking.contact_number if payment.booking else 'N/A',
            'customer_email': payment.booking.email if payment.booking else 'N/A',
            'booking_id': f"#{payment.booking.id}" if payment.booking else 'N/A',
            'movie_title': payment.booking.show.movie.title if payment.booking and payment.booking.show and payment.booking.show.movie else 'N/A',
            'screen_name': payment.booking.show.screen.name if payment.booking and payment.booking.show and payment.booking.show.screen else 'N/A',
            'show_date': payment.booking.show.show_date.strftime('%d %b %Y') if payment.booking and payment.booking.show and payment.booking.show.show_date else 'N/A',
            'show_time': payment.booking.show.show_time.strftime('%H:%M') if payment.booking and payment.booking.show and payment.booking.show.show_time else 'N/A',
            'seats': payment.booking.seats if payment.booking and payment.booking.seats else 'N/A',
            'amount': float(payment.amount) if payment.amount else 0,
            'notes': payment.notes,
            'refund_info': {},
            'paypal_info': {},
            'card_info': {},
            'upi_info': {}
        }
        
        # Add payment method specific details
        if payment.mode == 'paypal':
            receipt_data['paypal_info'] = {
                'order_id': payment.paypal_order_id,
                'capture_id': payment.paypal_capture_id,
                'payment_status': payment.paypal_payment_status
            }
        elif payment.mode == 'card':
            receipt_data['card_info'] = {
                'card_type': payment.card_type.title() if payment.card_type else 'N/A',
                'card_last_4': payment.card_last_4,
                'expiry': f"{payment.card_expiry_month}/{payment.card_expiry_year}" if payment.card_expiry_month and payment.card_expiry_year else 'N/A',
                'auth_code': payment.card_authorization_code
            }
        elif payment.mode == 'upi':
            receipt_data['upi_info'] = {
                'upi_id': payment.upi_id,
                'transaction_id': payment.upi_transaction_id,
                'utr_number': payment.utr_number
            }
        
        # Add refund information if applicable
        if payment.is_refunded():
            receipt_data['refund_info'] = {
                'refund_amount': float(payment.refund_amount) if payment.refund_amount else 0,
                'refund_reason': payment.refund_reason.replace('_', ' ').title() if payment.refund_reason else 'N/A',
                'refund_method': payment.refund_method.replace('_', ' ').title() if payment.refund_method else 'N/A',
                'refund_reference': payment.refund_reference_id,
                'refund_notes': payment.refund_notes
            }
        
        # Generate PDF using utility
        from app.utils import generate_payment_receipt_pdf
        pdf_data = generate_payment_receipt_pdf(receipt_data)
        
        # Create response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=receipt_{payment_id}.pdf'
        
        return response
    
    except Exception as e:
        ErrorLogger.log_error(e, request, user_id=current_user.id, context={'payment_id': payment_id})
        logger.error(f"Error generating PDF receipt: {str(e)}")
        flash('An error occurred while generating PDF receipt', 'danger')
        return redirect(url_for('payments.receipt', id=payment_id))