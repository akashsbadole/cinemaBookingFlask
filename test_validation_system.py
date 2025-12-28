"""
Comprehensive test suite for the enhanced validation and error handling system.
Tests input sanitization, security validation, data validation, business rules,
database constraints, real-time validation, and error handling.
"""

import unittest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Import the modules to test
from app.enhanced_validators import (
    AsyncValidators, BusinessRuleValidators, DatabaseConstraintValidators,
    RealTimeValidationManager, ValidationAuditor,
    validate_unique_field, validate_async_field, validate_business_rules
)
from app.validators import InputSanitizer, SecurityValidator, DataValidators
from app.validation_api import validate_field, validate_booking, validate_payment, validate_security
from app.error_handlers import ErrorHandler


class TestInputSanitization(unittest.TestCase):
    """Test input sanitization functionality."""
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        # Test normal string
        self.assertEqual(InputSanitizer.sanitize_string("Hello World"), "Hello World")
        
        # Test string with HTML tags
        self.assertEqual(InputSanitizer.sanitize_string("<script>alert('xss')</script>"), "alert('xss')")
        
        # Test string with SQL injection attempts
        self.assertEqual(InputSanitizer.sanitize_string("'; DROP TABLE users; --"), "'; DROP TABLE users; --")
        
        # Test empty string
        self.assertEqual(InputSanitizer.sanitize_string(""), "")
        
        # Test None value
        self.assertIsNone(InputSanitizer.sanitize_string(None))
    
    def test_sanitize_email(self):
        """Test email sanitization."""
        # Test valid email
        self.assertEqual(InputSanitizer.sanitize_email("user@example.com"), "user@example.com")
        
        # Test email with HTML
        self.assertEqual(InputSanitizer.sanitize_email("<script>user@example.com</script>"), "user@example.com")
        
        # Test None value
        self.assertIsNone(InputSanitizer.sanitize_email(None))
    
    def test_sanitize_phone(self):
        """Test phone number sanitization."""
        # Test normal phone
        self.assertEqual(InputSanitizer.sanitize_phone("123-456-7890"), "123-456-7890")
        
        # Test phone with extra characters
        self.assertEqual(InputSanitizer.sanitize_phone("(123) 456-7890"), "(123) 456-7890")
        
        # Test None value
        self.assertIsNone(InputSanitizer.sanitize_phone(None))
    
    def test_sanitize_numeric(self):
        """Test numeric sanitization."""
        # Test valid integer
        self.assertEqual(InputSanitizer.sanitize_numeric("123"), 123)
        
        # Test valid float
        self.assertEqual(InputSanitizer.sanitize_numeric("123.45"), 123.45)
        
        # Test invalid numeric
        self.assertIsNone(InputSanitizer.sanitize_numeric("abc"))
        
        # Test None value
        self.assertIsNone(InputSanitizer.sanitize_numeric(None))


class TestSecurityValidation(unittest.TestCase):
    """Test security validation functionality."""
    
    def test_detect_sql_injection(self):
        """Test SQL injection detection."""
        # Test SQL injection patterns
        self.assertTrue(SecurityValidator.detect_sql_injection("'; DROP TABLE users; --"))
        self.assertTrue(SecurityValidator.detect_sql_injection("' OR '1'='1"))
        self.assertTrue(SecurityValidator.detect_sql_injection("UNION SELECT * FROM users"))
        
        # Test safe strings
        self.assertFalse(SecurityValidator.detect_sql_injection("Hello World"))
        self.assertFalse(SecurityValidator.detect_sql_injection("user@example.com"))
    
    def test_detect_xss(self):
        """Test XSS detection."""
        # Test XSS patterns
        self.assertTrue(SecurityValidator.detect_xss("<script>alert('xss')</script>"))
        self.assertTrue(SecurityValidator.detect_xss("javascript:alert('xss')"))
        self.assertTrue(SecurityValidator.detect_xss("<img src=x onerror=alert('xss')>"))
        
        # Test safe strings
        self.assertFalse(SecurityValidator.detect_xss("Hello World"))
        self.assertFalse(SecurityValidator.detect_xss("user@example.com"))
    
    def test_validate_csrf_token(self):
        """Test CSRF token validation."""
        # Test matching tokens
        self.assertTrue(SecurityValidator.validate_csrf_token("token123", "token123"))
        
        # Test mismatching tokens
        self.assertFalse(SecurityValidator.validate_csrf_token("token123", "token456"))
        
        # Test empty tokens
        self.assertFalse(SecurityValidator.validate_csrf_token("", "token456"))
    
    def test_validate_file_upload(self):
        """Test file upload validation."""
        # Test allowed file types
        self.assertTrue(SecurityValidator.validate_file_upload("document.pdf", ["pdf", "doc", "docx"]))
        
        # Test disallowed file types
        self.assertFalse(SecurityValidator.validate_file_upload("script.exe", ["pdf", "doc", "docx"]))
        
        # Test dangerous file names
        self.assertFalse(SecurityValidator.validate_file_upload("../../etc/passwd", ["txt"]))


class TestDataValidation(unittest.TestCase):
    """Test data validation functionality."""
    
    def test_validate_email_format(self):
        """Test email format validation."""
        # Test valid emails
        self.assertTrue(DataValidator.validate_email_format("user@example.com"))
        self.assertTrue(DataValidator.validate_email_format("test.email+tag@example.co.uk"))
        
        # Test invalid emails
        self.assertFalse(DataValidator.validate_email_format("user@"))
        self.assertFalse(DataValidator.validate_email_format("@example.com"))
        self.assertFalse(DataValidator.validate_email_format("user.example.com"))
    
    def test_validate_phone_format(self):
        """Test phone format validation."""
        # Test valid phone numbers
        self.assertTrue(DataValidator.validate_phone_format("123-456-7890"))
        self.assertTrue(DataValidator.validate_phone_format("(123) 456-7890"))
        self.assertTrue(DataValidator.validate_phone_format("1234567890"))
        
        # Test invalid phone numbers
        self.assertFalse(DataValidator.validate_phone_format("123"))
        self.assertFalse(DataValidator.validate_phone_format("abc-def-ghij"))
    
    def test_validate_date_range(self):
        """Test date range validation."""
        # Test valid date range
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7)
        self.assertTrue(DataValidator.validate_date_range(start_date, end_date))
        
        # Test invalid date range (end before start)
        end_date = start_date - timedelta(days=7)
        self.assertFalse(DataValidator.validate_date_range(start_date, end_date))
    
    def test_validate_numeric_range(self):
        """Test numeric range validation."""
        # Test valid range
        self.assertTrue(DataValidator.validate_numeric_range(50, 1, 100))
        
        # Test invalid range (below minimum)
        self.assertFalse(DataValidator.validate_numeric_range(0, 1, 100))
        
        # Test invalid range (above maximum)
        self.assertFalse(DataValidator.validate_numeric_range(150, 1, 100))


class TestBusinessRuleValidation(unittest.TestCase):
    """Test business rule validation functionality."""
    
    def test_validate_seat_availability(self):
        """Test seat availability validation."""
        # Test available seat
        mock_seat = Mock()
        mock_seat.is_available = True
        self.assertTrue(BusinessRuleValidators.validate_seat_availability(mock_seat))
        
        # Test unavailable seat
        mock_seat.is_available = False
        self.assertFalse(BusinessRuleValidators.validate_seat_availability(mock_seat))
    
    def test_validate_show_capacity(self):
        """Test show capacity validation."""
        # Test within capacity
        self.assertTrue(BusinessRuleValidators.validate_show_capacity(50, 100))
        
        # Test at capacity
        self.assertTrue(BusinessRuleValidators.validate_show_capacity(100, 100))
        
        # Test over capacity
        self.assertFalse(BusinessRuleValidators.validate_show_capacity(150, 100))
    
    def test_validate_payment_amount(self):
        """Test payment amount validation."""
        # Test valid payment amount
        self.assertTrue(BusinessRuleValidators.validate_payment_amount(100, 100))
        
        # Test insufficient payment
        self.assertFalse(BusinessRuleValidators.validate_payment_amount(50, 100))
        
        # Test overpayment
        self.assertTrue(BusinessRuleValidators.validate_payment_amount(150, 100))
    
    def test_validate_refund_eligibility(self):
        """Test refund eligibility validation."""
        # Test eligible refund (within 24 hours)
        booking_time = datetime.now() - timedelta(hours=12)
        self.assertTrue(BusinessRuleValidators.validate_refund_eligibility(booking_time, 24))
        
        # Test ineligible refund (beyond 24 hours)
        booking_time = datetime.now() - timedelta(hours=48)
        self.assertFalse(BusinessRuleValidators.validate_refund_eligibility(booking_time, 24))


class TestDatabaseConstraintValidation(unittest.TestCase):
    """Test database constraint validation functionality."""
    
    def test_validate_foreign_key(self):
        """Test foreign key validation."""
        # Test existing foreign key
        with patch('app.database.db.session.execute') as mock_execute:
            mock_execute.return_value.fetchone.return_value = (1,)
            self.assertTrue(DatabaseConstraintValidators.validate_foreign_key("users", 1))
        
        # Test non-existing foreign key
        with patch('app.database.db.session.execute') as mock_execute:
            mock_execute.return_value.fetchone.return_value = None
            self.assertFalse(DatabaseConstraintValidators.validate_foreign_key("users", 999))
    
    def test_validate_unique_constraint(self):
        """Test unique constraint validation."""
        # Test unique value
        with patch('app.database.db.session.execute') as mock_execute:
            mock_execute.return_value.fetchone.return_value = None
            self.assertTrue(DatabaseConstraintValidators.validate_unique_constraint("users", "email", "test@example.com"))
        
        # Test duplicate value
        with patch('app.database.db.session.execute') as mock_execute:
            mock_execute.return_value.fetchone.return_value = (1,)
            self.assertFalse(DatabaseConstraintValidators.validate_unique_constraint("users", "email", "test@example.com"))
    
    def test_validate_check_constraint(self):
        """Test check constraint validation."""
        # Test valid check constraint
        self.assertTrue(DatabaseConstraintValidators.validate_check_constraint("age", 25, ">= 18"))
        
        # Test invalid check constraint
        self.assertFalse(DatabaseConstraintValidators.validate_check_constraint("age", 16, ">= 18"))


class TestRealTimeValidationManager(unittest.TestCase):
    """Test real-time validation manager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.manager = RealTimeValidationManager()
    
    def test_cache_validation_result(self):
        """Test caching validation results."""
        # Cache a validation result
        self.manager.cache_validation_result("email", "test@example.com", True)
        
        # Check if result is cached
        self.assertTrue(self.manager.is_cached("email", "test@example.com"))
    
    def test_get_cached_result(self):
        """Test retrieving cached validation results."""
        # Cache a validation result
        self.manager.cache_validation_result("email", "test@example.com", True)
        
        # Retrieve cached result
        result = self.manager.get_cached_result("email", "test@example.com")
        self.assertTrue(result)
    
    def test_clear_cache(self):
        """Test clearing validation cache."""
        # Cache a validation result
        self.manager.cache_validation_result("email", "test@example.com", True)
        
        # Clear cache
        self.manager.clear_cache()
        
        # Check if cache is cleared
        self.assertFalse(self.manager.is_cached("email", "test@example.com"))
    
    def test_is_expired(self):
        """Test cache expiration."""
        # Cache a validation result
        self.manager.cache_validation_result("email", "test@example.com", True)
        
        # Test if cache is expired (should not be expired immediately)
        self.assertFalse(self.manager.is_expired("email", "test@example.com"))


class TestValidationAuditor(unittest.TestCase):
    """Test validation auditor functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.auditor = ValidationAuditor()
    
    def test_log_validation_success(self):
        """Test logging validation success."""
        with patch('app.utils_audit.log_security_event') as mock_log:
            self.auditor.log_validation_success("email", "test@example.com", "user123")
            mock_log.assert_called_once()
    
    def test_log_validation_failure(self):
        """Test logging validation failure."""
        with patch('app.utils_audit.log_security_event') as mock_log:
            self.auditor.log_validation_failure("email", "test@example.com", "Invalid format", "user123")
            mock_log.assert_called_once()
    
    def test_log_security_violation(self):
        """Test logging security violations."""
        with patch('app.utils_audit.log_security_event') as mock_log:
            self.auditor.log_security_violation("sql_injection", "'; DROP TABLE users; --", "user123")
            mock_log.assert_called_once()
    
    def test_get_validation_stats(self):
        """Test retrieving validation statistics."""
        # Log some validation events
        with patch('app.utils_audit.log_security_event'):
            self.auditor.log_validation_success("email", "test@example.com", "user123")
            self.auditor.log_validation_failure("email", "invalid-email", "Invalid format", "user123")
        
        # Get stats
        stats = self.auditor.get_validation_stats()
        self.assertEqual(stats['success_count'], 1)
        self.assertEqual(stats['failure_count'], 1)


class TestErrorHandling(unittest.TestCase):
    """Test error handling functionality."""
    
    def test_handle_validation_error(self):
        """Test validation error handling."""
        error = ValueError("Invalid email format")
        
        with patch('flask.render_template') as mock_render:
            mock_render.return_value = "Error page"
            
            with patch('flask.current_app.logger') as mock_logger:
                response = handle_validation_error(error)
                
                # Check if error was logged
                mock_logger.error.assert_called()
                
                # Check if error page was rendered
                mock_render.assert_called()
    
    def test_handle_security_error(self):
        """Test security error handling."""
        error = SecurityError("SQL injection attempt detected")
        
        with patch('flask.render_template') as mock_render:
            mock_render.return_value = "Error page"
            
            with patch('flask.current_app.logger') as mock_logger:
                response = handle_security_error(error)
                
                # Check if error was logged
                mock_logger.error.assert_called()
                
                # Check if error page was rendered
                mock_render.assert_called()


class TestIntegration(unittest.TestCase):
    """Integration tests for the validation system."""
    
    def test_end_to_end_validation_flow(self):
        """Test end-to-end validation flow."""
        # Test field validation API
        with patch('app.validation_api.request') as mock_request:
            mock_request.json = {
                'field_name': 'email',
                'field_value': 'test@example.com',
                'context': {}
            }
            
            with patch('flask.jsonify') as mock_jsonify:
                result = validate_field()
                mock_jsonify.assert_called()
    
    def test_booking_validation_flow(self):
        """Test booking validation flow."""
        with patch('app.validation_api.request') as mock_request:
            mock_request.json = {
                'show_id': 1,
                'seat_ids': [1, 2, 3],
                'customer_id': 1
            }
            
            with patch('flask.jsonify') as mock_jsonify:
                result = validate_booking()
                mock_jsonify.assert_called()
    
    def test_payment_validation_flow(self):
        """Test payment validation flow."""
        with patch('app.validation_api.request') as mock_request:
            mock_request.json = {
                'booking_id': 1,
                'amount': 100,
                'payment_method': 'credit_card'
            }
            
            with patch('flask.jsonify') as mock_jsonify:
                result = validate_payment()
                mock_jsonify.assert_called()
    
    def test_security_validation_flow(self):
        """Test security validation flow."""
        with patch('app.validation_api.request') as mock_request:
            mock_request.json = {
                'input': 'test@example.com',
                'input_type': 'email'
            }
            
            with patch('flask.jsonify') as mock_jsonify:
                result = validate_security()
                mock_jsonify.assert_called()


class SecurityError(Exception):
    """Custom security error for testing."""
    pass


def run_validation_tests():
    """Run all validation tests and return results."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestInputSanitization,
        TestSecurityValidation,
        TestDataValidation,
        TestBusinessRuleValidation,
        TestDatabaseConstraintValidation,
        TestRealTimeValidationManager,
        TestValidationAuditor,
        TestErrorHandling,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Calculate success rate
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / (result.testsRun * 100))
    
    # Return results
    return {
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'success_rate': success_rate,
        'success': result.wasSuccessful()
    }


if __name__ == '__main__':
    print("Running Validation System Tests")
    print("=" * 50)
    
    results = run_validation_tests()
    
    print("\nTest Results:")
    print(f"Tests Run: {results['tests_run']}")
    print(f"Failures: {results['failures']}")
    print(f"Errors: {results['errors']}")
    print(f"Success Rate: {results['success_rate']:.2f}%")
    print(f"Overall Success: {results['success']}")
    
    if results['success']:
        print("\n✅ All validation tests passed!")
    else:
        print("\n❌ Some validation tests failed. Please review the output above.")