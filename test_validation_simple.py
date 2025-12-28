"""
Simple validation system test to verify core functionality
"""
import unittest
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_basic_validation_imports():
    """Test that validation modules can be imported"""
    try:
        from app.validators import InputSanitizer, SecurityValidator
        from app.enhanced_validators import AsyncValidators, BusinessRuleValidators
        print("All validation modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_basic_validation_functionality():
    """Test basic validation functionality"""
    try:
        from app.validators import InputSanitizer, SecurityValidator, DataValidators
        
        # Test input sanitization
        sanitized = InputSanitizer.sanitize_string("Hello World")
        assert sanitized == "Hello World", f"Expected 'Hello World', got '{sanitized}'"
        
        # Test email sanitization
        email = InputSanitizer.sanitize_email("user@example.com")
        assert email == "user@example.com", f"Expected 'user@example.com', got '{email}'"
        
        # Test SQL injection detection
        is_injection = SecurityValidator.detect_sql_injection("'; DROP TABLE users; --")
        assert is_injection == True, "SQL injection detection failed"
        
        # Test XSS detection
        is_xss = SecurityValidator.detect_xss("<script>alert('xss')</script>")
        assert is_xss == True, "XSS detection failed"
        
        # Test username validation
        is_valid_username = DataValidators.validate_username_format("testuser")
        assert is_valid_username == True, "Username validation failed"
        
        # Test email validation
        is_valid_email = DataValidators.validate_email_format("test@example.com")
        assert is_valid_email == True, "Email validation failed"
        
        print("Basic validation functionality tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Basic validation test failed: {e}")
        return False

def test_enhanced_validators():
    """Test enhanced validators"""
    try:
        from app.enhanced_validators import AsyncValidators, BusinessRuleValidators, ValidationAuditor
        
        # Test business rule validation
        is_valid, message = BusinessRuleValidators.validate_booking_time_restrictions(1, 1)
        # Should fail without proper show setup
        assert message is not None, "Business rule validation should return message"
        
        # Test validation auditor
        auditor = ValidationAuditor()
        auditor.log_validation_success("email", "test@example.com", {"test": True})
        print("✅ Enhanced validators tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced validators test failed: {e}")
        return False

def test_error_handlers():
    """Test error handlers"""
    try:
        from app.error_handlers import ErrorHandler, ErrorLogger
        
        # Test error logger
        ErrorLogger.log_error("Test error", {"test": True})
        
        # Test error handler
        error_handler = ErrorHandler()
        print("✅ Error handler tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Error handler test failed: {e}")
        return False

def run_simple_tests():
    """Run all simple tests"""
    print("Running Simple Validation System Tests")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_basic_validation_imports),
        ("Basic Validation Tests", test_basic_validation_functionality),
        ("Enhanced Validators Tests", test_enhanced_validators),
        ("Error Handler Tests", test_error_handlers)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}...")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"Test Results:")
    print(f"Tests Run: {total}")
    print(f"Tests Passed: {passed}")
    print(f"Tests Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.2f}%")
    
    if passed == total:
        print("\n🎉 All validation system tests passed!")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Please review the implementation.")
        return False

if __name__ == '__main__':
    success = run_simple_tests()
    sys.exit(0 if success else 1)