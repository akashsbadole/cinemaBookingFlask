/**
 * Client-side Validation Utility for Cinema Management System
 * Provides real-time validation feedback and security checks
 */

class FormValidator {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.options = {
            validateOnBlur: options.validateOnBlur !== false,
            validateOnChange: options.validateOnChange !== false,
            showErrorsInline: options.showErrorsInline !== false,
            errorClass: options.errorClass || 'is-invalid',
            successClass: options.successClass || 'is-valid',
            errorContainer: options.errorContainer || null,
            onSubmit: options.onSubmit || null,
            customValidators: options.customValidators || {}
        };
        
        this.fields = {};
        this.errors = {};
        this.init();
    }

    init() {
        // Find all form fields with validation rules
        const fields = this.form.querySelectorAll('[data-validate]');
        
        fields.forEach(field => {
            const rules = field.dataset.validate ? field.dataset.validate.split('|') : [];
            this.addField(field, rules);
        });

        // Add event listeners
        this.addEventListeners();
        
        // Setup error container if not provided
        if (!this.options.errorContainer) {
            this.options.errorContainer = this.createErrorContainer();
            this.form.appendChild(this.options.errorContainer);
        }
    }

    addField(field, rules) {
        const fieldName = field.name || field.id;
        if (!fieldName) return;

        this.fields[fieldName] = {
            element: field,
            rules: rules,
            isValid: false,
            validated: false
        };

        // Add validation attributes
        this.addValidationAttributes(field, rules);
    }

    addValidationAttributes(field, rules) {
        // Add HTML5 validation attributes based on rules
        rules.forEach(rule => {
            switch (rule) {
                case 'required':
                    field.required = true;
                    break;
                case 'email':
                    field.type = 'email';
                    field.pattern = '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$';
                    break;
                case 'phone':
                    field.pattern = '[0-9]{10}';
                    field.maxLength = 15;
                    break;
                case 'numeric':
                    field.pattern = '[0-9.]+';
                    break;
                case 'integer':
                    field.pattern = '[0-9]+';
                    break;
            }
        });
    }

    addEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (this.validateAll()) {
                if (this.options.onSubmit) {
                    this.options.onSubmit(this.form);
                } else {
                    this.form.submit();
                }
            }
        });

        // Field validation on blur/change
        Object.keys(this.fields).forEach(fieldName => {
            const field = this.fields[fieldName];
            
            if (this.options.validateOnBlur) {
                field.element.addEventListener('blur', () => {
                    this.validateField(fieldName);
                });
            }
            
            if (this.options.validateOnChange) {
                field.element.addEventListener('input', () => {
                    this.validateField(fieldName);
                });
            }
        });
    }

    validateField(fieldName) {
        const field = this.fields[fieldName];
        if (!field) return true;

        const value = field.element.value;
        const rules = field.rules;
        let isValid = true;
        let errors = [];

        // Run each validation rule
        rules.forEach(rule => {
            const result = this.runValidation(rule, value, field.element);
            if (!result.valid) {
                isValid = false;
                errors.push(result.message);
            }
        });

        // Update field state
        field.isValid = isValid;
        field.validated = true;
        this.updateFieldUI(field, errors);

        return isValid;
    }

    runValidation(rule, value, element) {
        const customValidator = this.options.customValidators[rule];
        
        // Check custom validator first
        if (customValidator) {
            return customValidator(value, element);
        }

        // Built-in validations
        switch (rule) {
            case 'required':
                return this.validateRequired(value);
            case 'email':
                return this.validateEmail(value);
            case 'phone':
                return this.validatePhone(value);
            case 'numeric':
                return this.validateNumeric(value);
            case 'integer':
                return this.validateInteger(value);
            case 'min-length':
                const minLength = parseInt(element.dataset.minLength) || 1;
                return this.validateMinLength(value, minLength);
            case 'max-length':
                const maxLength = parseInt(element.dataset.maxLength) || 100;
                return this.validateMaxLength(value, maxLength);
            case 'password-strength':
                return this.validatePasswordStrength(value);
            case 'card-number':
                return this.validateCardNumber(value);
            case 'expiry-date':
                return this.validateExpiryDate(value);
            case 'cvv':
                return this.validateCVV(value);
            case 'upi-id':
                return this.validateUPIId(value);
            case 'seat-selection':
                return this.validateSeatSelection(value);
            default:
                return { valid: true, message: '' };
        }
    }

    // Built-in validation methods
    validateRequired(value) {
        const isValid = value && value.trim().length > 0;
        return {
            valid: isValid,
            message: isValid ? '' : 'This field is required'
        };
    }

    validateEmail(value) {
        if (!value) return { valid: true, message: '' };
        
        const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        const isValid = emailPattern.test(value);
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Please enter a valid email address'
        };
    }

    validatePhone(value) {
        if (!value) return { valid: true, message: '' };
        
        // Remove non-digit characters
        const digits = value.replace(/\D/g, '');
        
        // Indian phone number validation
        const isValid = digits.length === 10 && digits[0] !== '0';
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Please enter a valid 10-digit phone number'
        };
    }

    validateNumeric(value) {
        if (!value) return { valid: true, message: '' };
        
        const num = parseFloat(value);
        const isValid = !isNaN(num) && isFinite(num);
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Please enter a valid number'
        };
    }

    validateInteger(value) {
        if (!value) return { valid: true, message: '' };
        
        const num = parseInt(value);
        const isValid = !isNaN(num) && Number.isInteger(num);
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Please enter a whole number'
        };
    }

    validateMinLength(value, minLength) {
        if (!value) return { valid: true, message: '' };
        
        const isValid = value.length >= minLength;
        
        return {
            valid: isValid,
            message: isValid ? '' : `Minimum length is ${minLength} characters`
        };
    }

    validateMaxLength(value, maxLength) {
        if (!value) return { valid: true, message: '' };
        
        const isValid = value.length <= maxLength;
        
        return {
            valid: isValid,
            message: isValid ? '' : `Maximum length is ${maxLength} characters`
        };
    }

    validatePasswordStrength(value) {
        if (!value) return { valid: true, message: '' };
        
        const checks = {
            length: value.length >= 8,
            uppercase: /[A-Z]/.test(value),
            lowercase: /[a-z]/.test(value),
            digit: /\d/.test(value),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(value)
        };
        
        const validScore = Object.values(checks).filter(Boolean).length;
        const isValid = validScore >= 4; // Require at least 4 out of 5
        
        const missing = [];
        if (!checks.length) missing.push('at least 8 characters');
        if (!checks.uppercase) missing.push('uppercase letter');
        if (!checks.lowercase) missing.push('lowercase letter');
        if (!checks.digit) missing.push('digit');
        if (!checks.special) missing.push('special character');
        
        return {
            valid: isValid,
            message: isValid ? '' : `Password must contain: ${missing.join(', ')}`
        };
    }

    validateCardNumber(value) {
        if (!value) return { valid: true, message: '' };
        
        // Remove spaces and dashes
        const cleanNumber = value.replace(/[\s-]/g, '');
        
        // Basic check
        if (!/^\d{13,19}$/.test(cleanNumber)) {
            return {
                valid: false,
                message: 'Card number must be 13-19 digits'
            };
        }
        
        // Luhn algorithm
        let sum = 0;
        const reverseDigits = cleanNumber.split('').reverse();
        
        for (let i = 0; i < reverseDigits.length; i++) {
            let digit = parseInt(reverseDigits[i]);
            if (i % 2 === 1) {
                digit *= 2;
                if (digit > 9) digit -= 9;
            }
            sum += digit;
        }
        
        const isValid = sum % 10 === 0;
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Invalid card number'
        };
    }

    validateExpiryDate(value) {
        if (!value) return { valid: true, message: '' };
        
        // Expected format: MM/YY
        const match = value.match(/^(\d{2})\/(\d{2})$/);
        if (!match) {
            return {
                valid: false,
                message: 'Format must be MM/YY'
            };
        }
        
        const month = parseInt(match[1]);
        const year = 2000 + parseInt(match[2]);
        const expiry = new Date(year, month, 0);
        const now = new Date();
        
        const isValid = expiry > now;
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Card has expired'
        };
    }

    validateCVV(value) {
        if (!value) return { valid: true, message: '' };
        
        const isValid = /^\d{3,4}$/.test(value);
        
        return {
            valid: isValid,
            message: isValid ? '' : 'CVV must be 3-4 digits'
        };
    }

    validateUPIId(value) {
        if (!value) return { valid: true, message: '' };
        
        const upiPattern = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$/;
        const isValid = upiPattern.test(value);
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Invalid UPI ID format (expected: username@provider)'
        };
    }

    validateSeatSelection(value) {
        if (!value) return { valid: true, message: '' };
        
        // Expected format: comma-separated seat IDs
        const seatIds = value.split(',').map(s => s.trim()).filter(s => s);
        
        if (seatIds.length === 0) {
            return {
                valid: false,
                message: 'Please select at least one seat'
            };
        }
        
        if (seatIds.length > 10) {
            return {
                valid: false,
                message: 'Maximum 10 seats can be selected at once'
            };
        }
        
        // Validate seat ID format
        const invalidSeats = seatIds.filter(seat => !/^[A-Z]\d+$/.test(seat));
        
        if (invalidSeats.length > 0) {
            return {
                valid: false,
                message: `Invalid seat format: ${invalidSeats.join(', ')}`
            };
        }
        
        return {
            valid: true,
            message: ''
        };
    }

    validateAll() {
        let isValid = true;
        this.errors = {};

        // Validate all fields
        Object.keys(this.fields).forEach(fieldName => {
            const fieldValid = this.validateField(fieldName);
            if (!fieldValid) {
                isValid = false;
                // Store errors
                const field = this.fields[fieldName];
                this.errors[fieldName] = this.getFieldErrors(field);
            }
        });

        // Show overall error message
        if (!isValid) {
            this.showOverallError();
        } else {
            this.clearOverallError();
        }

        return isValid;
    }

    getFieldErrors(field) {
        const value = field.element.value;
        const errors = [];

        field.rules.forEach(rule => {
            const result = this.runValidation(rule, value, field.element);
            if (!result.valid) {
                errors.push(result.message);
            }
        });

        return errors;
    }

    updateFieldUI(field, errors) {
        const element = field.element;
        
        // Update CSS classes
        element.classList.remove(this.options.errorClass, this.options.successClass);
        
        if (errors.length > 0) {
            element.classList.add(this.options.errorClass);
            
            // Show inline errors if enabled
            if (this.options.showErrorsInline) {
                this.showInlineError(element, errors);
            }
        } else {
            element.classList.add(this.options.successClass);
            this.clearInlineError(element);
        }
    }

    showInlineError(element, errors) {
        this.clearInlineError(element);
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = errors[0]; // Show first error
        
        // Insert after the element
        element.parentNode.insertBefore(errorDiv, element.nextSibling);
    }

    clearInlineError(element) {
        const existingError = element.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
    }

    createErrorContainer() {
        const container = document.createElement('div');
        container.className = 'alert alert-danger validation-error-container';
        container.style.display = 'none';
        return container;
    }

    showOverallError() {
        const errorContainer = this.options.errorContainer;
        errorContainer.style.display = 'block';
        
        let errorHtml = '<div><i class="fas fa-exclamation-triangle me-2"></i>Please fix the following errors:</div><ul>';
        
        Object.keys(this.errors).forEach(fieldName => {
            this.errors[fieldName].forEach(error => {
                errorHtml += `<li>${fieldName}: ${error}</li>`;
            });
        });
        
        errorHtml += '</ul>';
        errorContainer.innerHTML = errorHtml;
    }

    clearOverallError() {
        const errorContainer = this.options.errorContainer;
        errorContainer.style.display = 'none';
        errorContainer.innerHTML = '';
    }
}

// Security validation utilities
class SecurityValidator {
    static sanitizeInput(input) {
        if (!input) return '';
        
        // Remove potentially dangerous characters
        return input
            .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            .trim();
    }

    static detectSQLInjection(input) {
        if (!input) return false;
        
        const sqlPatterns = [
            /(\bUNION\b.*\bSELECT\b)/gi,
            /(\bSELECT\b.*\bFROM\b)/gi,
            /(\bINSERT\b.*\bINTO\b)/gi,
            /(\bUPDATE\b.*\bSET\b)/gi,
            /(\bDELETE\b.*\bFROM\b)/gi,
            /(\bDROP\b.*\bTABLE\b)/gi,
            /(\/\*|\*\/|--|;|'|"|`|exec|xp_cmdshell)/gi
        ];
        
        return sqlPatterns.some(pattern => pattern.test(input));
    }

    static detectXSS(input) {
        if (!input) return false;
        
        const xssPatterns = [
            /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
            /javascript:/gi,
            /on\w+\s*=/gi,
            /<iframe\b[^>]*>/gi,
            /<object\b[^>]*>/gi,
            /<embed\b[^>]*>/gi,
            /eval\s*\(/gi,
            /expression\s*\(/gi
        ];
        
        return xssPatterns.some(pattern => pattern.test(input));
    }

    static sanitizeForDisplay(input) {
        if (!input) return '';
        
        // HTML encode special characters
        const div = document.createElement('div');
        div.textContent = input;
        return div.innerHTML;
    }
}

// Utility functions
const ValidationUtils = {
    // Initialize validation for all forms with data-validation="enabled"
    initAllForms: function() {
        document.querySelectorAll('form[data-validation="enabled"]').forEach(form => {
            new FormValidator(form, {
                validateOnBlur: true,
                validateOnChange: true,
                showErrorsInline: true,
                customValidators: this.getCustomValidators()
            });
        });
    },

    // Get custom validators from data attributes
    getCustomValidators: function() {
        const validators = {};
        
        // Password confirmation validator
        validators['password-confirm'] = (value, element) => {
            const passwordField = document.getElementById(element.dataset.passwordMatch);
            if (!passwordField) return { valid: true, message: '' };
            
            const isValid = value === passwordField.value;
            return {
                valid: isValid,
                message: isValid ? '' : 'Passwords do not match'
            };
        };

        // Date range validator
        validators['date-range'] = (value, element) => {
            if (!value) return { valid: true, message: '' };
            
            const minDate = element.dataset.minDate ? new Date(element.dataset.minDate) : null;
            const maxDate = element.dataset.maxDate ? new Date(element.dataset.maxDate) : null;
            const inputDate = new Date(value);
            
            if (minDate && inputDate < minDate) {
                return {
                    valid: false,
                    message: 'Date cannot be before ' + minDate.toLocaleDateString()
                };
            }
            
            if (maxDate && inputDate > maxDate) {
                return {
                    valid: false,
                    message: 'Date cannot be after ' + maxDate.toLocaleDateString()
                };
            }
            
            return { valid: true, message: '' };
        };

        return validators;
    },

    // Format phone number as user types
    formatPhone: function(input) {
        let value = input.value.replace(/\D/g, '');
        
        // Limit to 10 digits
        if (value.length > 10) {
            value = value.slice(0, 10);
        }
        
        // Format as XXX-XXX-XXXX or (XXX) XXX-XXXX
        if (value.length <= 3) {
            input.value = value;
        } else if (value.length <= 6) {
            input.value = value.slice(0, 3) + '-' + value.slice(3);
        } else {
            input.value = value.slice(0, 3) + '-' + value.slice(3, 6) + '-' + value.slice(6);
        }
    },

    // Format card number as user types
    formatCardNumber: function(input) {
        let value = input.value.replace(/\s/g, '');
        let formattedValue = '';
        
        // Add spaces every 4 digits
        for (let i = 0; i < value.length; i++) {
            if (i > 0 && i % 4 === 0) {
                formattedValue += ' ';
            }
            formattedValue += value[i];
        }
        
        input.value = formattedValue;
    },

    // Setup input formatting for specific fields
    setupInputFormatting: function() {
        // Phone number formatting
        document.querySelectorAll('input[data-format="phone"]').forEach(input => {
            input.addEventListener('input', function() {
                ValidationUtils.formatPhone(this);
            });
        });

        // Card number formatting
        document.querySelectorAll('input[data-format="card"]').forEach(input => {
            input.addEventListener('input', function() {
                ValidationUtils.formatCardNumber(this);
            });
        });

        // Auto-sanitize sensitive inputs
        document.querySelectorAll('textarea[data-auto-sanitize="true"]').forEach(textarea => {
            textarea.addEventListener('blur', function() {
                this.value = SecurityValidator.sanitizeInput(this.value);
            });
        });
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    ValidationUtils.initAllForms();
    ValidationUtils.setupInputFormatting();
});

// Export for use in other scripts
window.FormValidator = FormValidator;
window.SecurityValidator = SecurityValidator;
window.ValidationUtils = ValidationUtils;