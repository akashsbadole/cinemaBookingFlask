"""
Validation API for real-time validation requests
"""
from flask import Blueprint, request, jsonify, current_app
from app.enhanced_validators import (
    AsyncValidators, 
    BusinessRuleValidators, 
    RealTimeValidationManager,
    ValidationAuditor
)
from app.validators import InputSanitizer, SecurityValidator
import asyncio
from functools import wraps
from datetime import datetime

validation_api = Blueprint('validation_api', __name__)
validation_manager = RealTimeValidationManager()


def async_route(f):
    """Decorator to handle async routes in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


@validation_api.route('/api/validate/field', methods=['POST'])
@async_route
async def validate_field():
    """
    Real-time field validation endpoint
    
    Expects JSON payload:
    {
        "field_name": "username",
        "field_value": "john_doe",
        "validation_type": "username_availability",
        "context": {
            "exclude_user_id": 123,
            "show_id": 456
        }
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'valid': False,
                'message': 'No data provided'
            }), 400
        
        field_name = data.get('field_name')
        field_value = data.get('field_value')
        validation_type = data.get('validation_type')
        context = data.get('context', {})
        
        # Validate required fields
        if not field_name or field_value is None or not validation_type:
            return jsonify({
                'valid': False,
                'message': 'Missing required fields: field_name, field_value, validation_type'
            }), 400
        
        # Sanitize input
        sanitized_value = InputSanitizer.sanitize_string(str(field_value))
        
        # Security validation
        security_result = SecurityValidator.validate_input(sanitized_value)
        if not security_result['is_safe']:
            ValidationAuditor.log_security_violation(
                'Malicious Input in Validation',
                {
                    'field_name': field_name,
                    'field_value': sanitized_value[:50],  # Limit for privacy
                    'validation_type': validation_type,
                    'security_issues': security_result['issues']
                },
                severity='high'
            )
            return jsonify({
                'valid': False,
                'message': 'Input contains potentially malicious content'
            }), 400
        
        # Perform validation
        result = await validation_manager.validate_field_async(
            field_name, 
            sanitized_value, 
            validation_type, 
            **context
        )
        
        # Log validation attempt
        ValidationAuditor.log_validation_attempt(
            field_name,
            sanitized_value,
            result,
            context
        )
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Validation API error: {str(e)}")
        return jsonify({
            'valid': False,
            'message': 'Validation service temporarily unavailable'
        }), 500


@validation_api.route('/api/validate/booking', methods=['POST'])
def validate_booking():
    """
    Validate booking data against business rules
    
    Expects JSON payload:
    {
        "show_id": 123,
        "seat_ids": [1, 2, 3],
        "user_id": 456,
        "proposed_price": 500.00
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'valid': False,
                'message': 'No data provided'
            }), 400
        
        show_id = data.get('show_id')
        seat_ids = data.get('seat_ids', [])
        user_id = data.get('user_id')
        proposed_price = data.get('proposed_price')
        
        # Validate required fields
        if not show_id or not seat_ids:
            return jsonify({
                'valid': False,
                'message': 'Missing required fields: show_id, seat_ids'
            }), 400
        
        # Validate booking time restrictions
        time_valid, time_error = BusinessRuleValidators.validate_booking_time_restrictions(
            show_id, user_id
        )
        if not time_valid:
            return jsonify({
                'valid': False,
                'message': time_error
            }), 400
        
        # Validate pricing rules
        if proposed_price:
            price_valid, price_error, calculated_price = BusinessRuleValidators.validate_pricing_rules(
                show_id, seat_ids, proposed_price
            )
            if not price_valid:
                return jsonify({
                    'valid': False,
                    'message': price_error,
                    'calculated_price': float(calculated_price) if calculated_price else None
                }), 400
        
        # Check seat availability
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            seat_result = loop.run_until_complete(
                AsyncValidators.validate_show_seat_availability(show_id, seat_ids)
            )
            loop.close()
            
            if not seat_result['valid']:
                return jsonify(seat_result), 400
                
        except Exception as e:
            current_app.logger.error(f"Seat availability check error: {str(e)}")
            return jsonify({
                'valid': False,
                'message': 'Error checking seat availability'
            }), 500
        
        return jsonify({
            'valid': True,
            'message': 'Booking validation successful'
        })
        
    except Exception as e:
        current_app.logger.error(f"Booking validation API error: {str(e)}")
        return jsonify({
            'valid': False,
            'message': 'Booking validation service temporarily unavailable'
        }), 500


@validation_api.route('/api/validate/payment', methods=['POST'])
def validate_payment():
    """
    Validate payment method and amount
    
    Expects JSON payload:
    {
        "user_id": 456,
        "payment_method": "card",
        "amount": 500.00
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'valid': False,
                'message': 'No data provided'
            }), 400
        
        user_id = data.get('user_id')
        payment_method = data.get('payment_method')
        amount = data.get('amount')
        
        # Validate required fields
        if not payment_method or amount is None:
            return jsonify({
                'valid': False,
                'message': 'Missing required fields: payment_method, amount'
            }), 400
        
        # Validate payment method limits
        payment_valid, payment_error = BusinessRuleValidators.validate_payment_method_limits(
            user_id, payment_method, amount
        )
        if not payment_valid:
            return jsonify({
                'valid': False,
                'message': payment_error
            }), 400
        
        return jsonify({
            'valid': True,
            'message': 'Payment validation successful'
        })
        
    except Exception as e:
        current_app.logger.error(f"Payment validation API error: {str(e)}")
        return jsonify({
            'valid': False,
            'message': 'Payment validation service temporarily unavailable'
        }), 500


@validation_api.route('/api/validate/security', methods=['POST'])
def validate_security():
    """
    Security validation endpoint for detecting malicious input
    
    Expects JSON payload:
    {
        "input_data": "User input to validate",
        "context": {
            "form_name": "registration",
            "field_name": "username"
        }
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'valid': False,
                'message': 'No data provided'
            }), 400
        
        input_data = data.get('input_data', '')
        context = data.get('context', {})
        
        # Sanitize and validate input
        sanitized_input = InputSanitizer.sanitize_string(input_data)
        security_result = SecurityValidator.validate_input(sanitized_input)
        
        # Log security violations if detected
        if not security_result['is_safe']:
            ValidationAuditor.log_security_violation(
                'Security Validation Failed',
                {
                    'input_data': sanitized_input[:100],  # Limit for privacy
                    'context': context,
                    'security_issues': security_result['issues']
                },
                severity='medium' if len(security_result['issues']) < 3 else 'high'
            )
        
        return jsonify(security_result)
        
    except Exception as e:
        current_app.logger.error(f"Security validation API error: {str(e)}")
        return jsonify({
            'valid': False,
            'message': 'Security validation service temporarily unavailable'
        }), 500


@validation_api.route('/api/validate/cache/clear', methods=['POST'])
def clear_validation_cache():
    """
    Clear validation cache (admin only)
    """
    try:
        # Check if user is admin (this would need proper authentication)
        # For now, just clear the cache
        validation_manager.clear_cache()
        
        return jsonify({
            'success': True,
            'message': 'Validation cache cleared successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Cache clear error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to clear validation cache'
        }), 500


@validation_api.route('/api/validate/health', methods=['GET'])
def validation_health_check():
    """
    Health check endpoint for validation service
    """
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'cache_size': len(validation_manager.validation_cache),
            'version': '1.0.0'
        })
        
    except Exception as e:
        current_app.logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500