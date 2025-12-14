/**
 * Enhanced Client-side Validation Utility for Cinema Management System
 * Provides real-time validation feedback and security checks
 */

class EnhancedFormValidator {
    constructor(formElement, options = {}) {
        this.form = formElement;
        this.options = {
            validateOnBlur: options.validateOnBlur !== false,
            validateOnChange: options.validateOnChange !== false,
            validateOnInput: options.validateOnInput !== false,
            showErrorsInline: options.showErrorsInline !== false,
            errorClass: options.errorClass || 'is-invalid',
            successClass: options.successClass || 'is-valid',
            warningClass: options.warningClass || 'is-warning',
            errorContainer: options.errorContainer || null,
            onSubmit: options.onSubmit || null,
            customValidators: options.customValidators || {},
            debounceDelay: options.debounceDelay || 300,
            showProgress: options.showProgress !== false,
            enableRealTimeValidation: options.enableRealTimeValidation !== false,
            enableAsyncValidation: options.enableAsyncValidation !== false
        };
        
        this.fields = {};
        this.errors = {};
        this.warnings = {};
        this.validationState = {};
        this.debounceTimers = {};
        this.asyncValidators = {};
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

        // Initialize validation state
        this.updateValidationState();
        
        // Store original submit button text
        const submitBtn = this.form.querySelector('button[type="submit"], input[type="submit"]');
        if (submitBtn) {
            submitBtn.setAttribute('data-original-text', submitBtn.innerHTML || submitBtn.value);
        }
    }

    addField(field, rules) {
        const fieldName = field.name || field.id;
        if (!fieldName) return;

        this.fields[fieldName] = {
            element: field,
            rules: rules,
            isValid: false,
            validated: false,
            hasWarning: false,
            asyncValidation: false
        };

        // Add validation attributes
        this.addValidationAttributes(field, rules);
        
        // Add real-time validation indicators
        this.addValidationIndicators(field);
    }

    addValidationAttributes(field, rules) {
        // Add HTML5 validation attributes based on rules
        rules.forEach(rule => {
            switch (rule) {
                case 'required':
                    field.required = true;
                    field.setAttribute('aria-required', 'true');
                    break;
                case 'email':
                    field.type = 'email';
                    field.pattern = '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$';
                    field.setAttribute('inputmode', 'email');
                    break;
                case 'phone':
                    field.pattern = '[0-9]{10}';
                    field.maxLength = 15;
                    field.setAttribute('inputmode', 'tel');
                    break;
                case 'numeric':
                    field.pattern = '[0-9.]+';
                    field.setAttribute('inputmode', 'decimal');
                    break;
                case 'integer':
                    field.pattern = '[0-9]+';
                    field.setAttribute('inputmode', 'numeric');
                    break;
            }
        });
    }

    addValidationIndicators(field) {
        // Add loading indicator for async validation
        const indicator = document.createElement('span');
        indicator.className = 'validation-indicator';
        indicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        indicator.style.display = 'none';
        indicator.style.marginLeft = '8px';
        
        // Insert after field or after form-group
        const parent = field.closest('.form-group') || field.parentNode;
        parent.appendChild(indicator);
        
        field.validationIndicator = indicator;
    }

    addEventListeners() {
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            if (this.validateAll()) {
                this.showProgress();
                if (this.options.onSubmit) {
                    this.options.onSubmit(this.form);
                } else {
                    this.form.submit();
                }
            } else {
                this.focusFirstError();
            }
        });

        // Field validation on blur/change/input
        Object.keys(this.fields).forEach(fieldName => {
            const field = this.fields[fieldName];
            const element = field.element;
            
            // Blur validation
            if (this.options.validateOnBlur) {
                element.addEventListener('blur', () => {
                    this.validateField(fieldName);
                });
            }
            
            // Change validation (for selects, checkboxes, radios)
            if (this.options.validateOnChange) {
                element.addEventListener('change', () => {
                    this.validateField(fieldName);
                });
            }
            
            // Real-time input validation with debouncing
            if (this.options.validateOnInput && this.options.enableRealTimeValidation) {
                element.addEventListener('input', (e) => {
                    this.debounceValidation(fieldName, e);
                });
            }
        });
    }

    debounceValidation(fieldName, event) {
        // Clear existing timer
        if (this.debounceTimers[fieldName]) {
            clearTimeout(this.debounceTimers[fieldName]);
        }
        
        // Set new timer
        this.debounceTimers[fieldName] = setTimeout(() => {
            this.validateField(fieldName, event);
        }, this.options.debounceDelay);
    }

    showProgress() {
        if (this.options.showProgress) {
            const submitBtn = this.form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            }
        }
    }

    hideProgress() {
        if (this.options.showProgress) {
            const submitBtn = this.form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = submitBtn.getAttribute('data-original-text') || 'Submit';
            }
        }
    }

    updateValidationState() {
        this.validationState = {
            totalFields: Object.keys(this.fields).length,
            validFields: Object.values(this.fields).filter(f => f.isValid).length,
            invalidFields: Object.values(this.fields).filter(f => !f.isValid && f.validated).length,
            fieldsWithWarnings: Object.values(this.fields).filter(f => f.hasWarning).length,
            hasErrors: Object.keys(this.errors).length > 0,
            hasWarnings: Object.keys(this.warnings).length > 0
        };
    }

    focusFirstError() {
        const firstInvalidField = Object.keys(this.fields).find(fieldName => 
            this.fields[fieldName].validated && !this.fields[fieldName].isValid
        );
        
        if (firstInvalidField) {
            const element = this.fields[firstInvalidField].element;
            element.focus();
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    validateField(fieldName, event = null) {
        const field = this.fields[fieldName];
        if (!field) return true;

        const value = field.element.value;
        const rules = field.rules;
        let isValid = true;
        let hasWarning = false;
        let errors = [];
        let warnings = [];

        // Show loading indicator for async validation
        if (field.asyncValidation) {
            field.validationIndicator.style.display = 'inline-block';
        }

        // Run each validation rule
        rules.forEach(rule => {
            const result = this.runValidation(rule, value, field.element, event);
            if (!result.valid) {
                isValid = false;
                errors.push(result.message);
            } else if (result.warning) {
                hasWarning = true;
                warnings.push(result.message);
            }
        });

        // Run custom validators
        if (this.options.customValidators[fieldName]) {
            const customResult = this.options.customValidators[fieldName](value, field.element);
            if (!customResult.valid) {
                isValid = false;
                errors.push(customResult.message);
            }
        }

        // Run async validation if enabled
        if (this.options.enableAsyncValidation && field.asyncValidation) {
            this.runAsyncValidation(fieldName, value);
        }

        // Update field state
        field.isValid = isValid;
        field.hasWarning = hasWarning;
        field.validated = true;
        this.updateFieldUI(field, errors, warnings);

        // Update global error/warning collections
        if (errors.length > 0) {
            this.errors[fieldName] = errors;
        } else {
            delete this.errors[fieldName];
        }

        if (warnings.length > 0) {
            this.warnings[fieldName] = warnings;
        } else {
            delete this.warnings[fieldName];
        }

        // Hide loading indicator
        if (field.validationIndicator) {
            field.validationIndicator.style.display = 'none';
        }

        // Update overall validation state
        this.updateValidationState();

        return isValid;
    }

    runAsyncValidation(fieldName, value) {
        const field = this.fields[fieldName];
        
        // Cancel previous async validation if exists
        if (this.asyncValidators[fieldName]) {
            this.asyncValidators[fieldName].abort();
        }

        // Create new abort controller
        const abortController = new AbortController();
        this.asyncValidators[fieldName] = abortController;

        // Simulate async validation (replace with actual API calls)
        setTimeout(() => {
            if (abortController.signal.aborted) return;

            // Example async validations
            if (fieldName === 'username') {
                this.validateUsernameAsync(fieldName, value);
            } else if (fieldName === 'email') {
                this.validateEmailAsync(fieldName, value);
            }
        }, 500);
    }

    async validateUsernameAsync(fieldName, value) {
        if (value.length < 3) return;

        try {
            // Simulate API call to check username availability
            const response = await fetch(`/api/validate/username?username=${encodeURIComponent(value)}`, {
                signal: this.asyncValidators[fieldName]?.signal
            });
            
            if (!response.ok) throw new Error('Validation failed');
            
            const result = await response.json();
            
            const field = this.fields[fieldName];
            if (!result.available) {
                field.hasWarning = true;
                this.warnings[fieldName] = ['Username is already taken'];
                this.updateFieldUI(field, [], this.warnings[fieldName]);
            }
        } catch (error) {
            console.error('Async validation failed:', error);
        }
    }

    async validateEmailAsync(fieldName, value) {
        if (!value.includes('@')) return;

        try {
            // Simulate API call to check email format/validity
            const response = await fetch(`/api/validate/email?email=${encodeURIComponent(value)}`, {
                signal: this.asyncValidators[fieldName]?.signal
            });
            
            if (!response.ok) throw new Error('Validation failed');
            
            const result = await response.json();
            
            const field = this.fields[fieldName];
            if (!result.valid) {
                field.isValid = false;
                this.errors[fieldName] = ['Invalid email format or domain'];
                this.updateFieldUI(field, this.errors[fieldName], []);
            }
        } catch (error) {
            console.error('Async validation failed:', error);
        }
    }

    runValidation(rule, value, element, event = null) {
        const customValidator = this.options.customValidators[rule];
        
        // Check custom validator first
        if (customValidator) {
            return customValidator(value, element, event);
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
            case 'show-time-conflict':
                return this.validateShowTimeConflict(value, element);
            case 'business-hours':
                return this.validateBusinessHours(value, element);
            default:
                return { valid: true, message: '' };
        }
    }

    // Enhanced validation methods
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
            warning: validScore === 3,
            message: isValid ? '' : `Password must contain: ${missing.join(', ')}`,
            warningMessage: validScore === 3 ? 'Password could be stronger' : ''
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

    validateShowTimeConflict(value, element) {
        // This would integrate with backend validation
        // For now, just basic validation
        if (!value) return { valid: true, message: '' };
        
        return {
            valid: true,
            message: ''
        };
    }

    validateBusinessHours(value, element) {
        if (!value) return { valid: true, message: '' };
        
        // Basic business hours validation (6 AM to 11:59 PM)
        const hour = parseInt(value.split(':')[0]);
        const isValid = hour >= 6 && hour <= 23;
        
        return {
            valid: isValid,
            message: isValid ? '' : 'Time must be between 6:00 AM and 11:59 PM'
        };
    }

    validateAll() {
        let isValid = true;
        this.errors = {};
        this.warnings = {};

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

    updateFieldUI(field, errors, warnings) {
        const element = field.element;
        
        // Update CSS classes
        element.classList.remove(this.options.errorClass, this.options.successClass, this.options.warningClass);
        
        if (errors.length > 0) {
            element.classList.add(this.options.errorClass);
            
            // Show inline errors if enabled
            if (this.options.showErrorsInline) {
                this.showInlineError(element, errors);
            }
        } else if (warnings.length > 0) {
            element.classList.add(this.options.warningClass);
            
            // Show inline warnings if enabled
            if (this.options.showErrorsInline) {
                this.showInlineWarning(element, warnings);
            }
        } else {
            element.classList.add(this.options.successClass);
            this.clearInlineError(element);
            this.clearInlineWarning(element);
        }
    }

    showInlineError(element, errors) {
        this.clearInlineError(element);
        this.clearInlineWarning(element);
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle me-1"></i>${errors[0]}`;
        
        // Insert after the element
        element.parentNode.insertBefore(errorDiv, element.nextSibling);
    }

    showInlineWarning(element, warnings) {
        this.clearInlineError(element);
        this.clearInlineWarning(element);
        
        const warningDiv = document.createElement('div');
        warningDiv.className = 'warning-feedback';
        warningDiv.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i>${warnings[0]}`;
        
        // Insert after the element
        element.parentNode.insertBefore(warningDiv, element.nextSibling);
    }

    clearInlineError(element) {
        const existingError = element.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
    }

    clearInlineWarning(element) {
        const existingWarning = element.parentNode.querySelector('.warning-feedback');
        if (existingWarning) {
            existingWarning.remove();
        }
    }

    createErrorContainer() {
        const container = document.createElement('div');
        container.className = 'alert alert-danger validation-error-container';
        container.style.display = 'none';
        container.setAttribute('role', 'alert');
        return container;
    }

    showOverallError() {
        const errorContainer = this.options.errorContainer;
        errorContainer.style.display = 'block';
        
        let errorHtml = '<div><i class="fas fa-exclamation-triangle me-2"></i>Please fix the following errors:</div><ul>';
        
        Object.keys(this.errors).forEach(fieldName => {
            this.errors[fieldName].forEach(error => {
                errorHtml += `<li><strong>${fieldName}:</strong> ${error}</li>`;
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

    // Public methods
    reset() {
        Object.keys(this.fields).forEach(fieldName => {
            const field = this.fields[fieldName];
            field.isValid = false;
            field.validated = false;
            field.hasWarning = false;
            this.updateFieldUI(field, [], []);
        });
        
        this.errors = {};
        this.warnings = {};
        this.updateValidationState();
        this.clearOverallError();
        this.hideProgress();
    }

    getValidationState() {
        return this.validationState;
    }

    getFieldValidation(fieldName) {
        const field = this.fields[fieldName];
        if (!field) return null;
        
        return {
            isValid: field.isValid,
            hasWarning: field.hasWarning,
            validated: field.validated,
            errors: this.errors[fieldName] || [],
            warnings: this.warnings[fieldName] || []
        };
    }
}

// Enhanced Security Validation
class EnhancedSecurityValidator {
    static sanitizeInput(input) {
        if (!input) return '';
        
        return input
            .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            .replace(/javascript:/gi, '')
            .replace(/on\w+\s*=/gi, '')
            .trim();
    }

    static detectAdvancedThreats(input) {
        if (!input) return false;
        
        const advancedPatterns = [
            /\b(base64|eval|exec|system|shell)\b/gi,
            /\b(union|select|insert|update|delete|drop|create|alter)\s+\w+/gi,
            /<iframe[^>]*>/gi,
            /<object[^>]*>/gi,
            /<embed[^>]*>/gi,
            /document\.(cookie|location|write)/gi,
            /window\.(location|open)/gi,
            /\.\.\//g,  // Directory traversal
        ];
        
        return advancedPatterns.some(pattern => pattern.test(input));
    }

    static validateFileSize(file, maxSizeMB = 5) {
        if (!file) return { valid: true, message: '' };
        
        const maxSizeBytes = maxSizeMB * 1024 * 1024;
        const isValid = file.size <= maxSizeBytes;
        
        return {
            valid: isValid,
            message: isValid ? '' : `File size cannot exceed ${maxSizeMB}MB`
        };
    }

    static validateFileType(file, allowedTypes = []) {
        if (!file) return { valid: true, message: '' };
        
        const isValid = allowedTypes.length === 0 || allowedTypes.includes(file.type);
        
        return {
            valid: isValid,
            message: isValid ? '' : `File type ${file.type} is not allowed`
        };
    }
}

// Utility functions for enhanced validation
const EnhancedValidationUtils = {
    // Initialize enhanced validation for all forms with data-validation="enhanced"
    initAllForms: function() {
        document.querySelectorAll('form[data-validation="enhanced"]').forEach(form => {
            new EnhancedFormValidator(form, {
                validateOnBlur: true,
                validateOnChange: true,
                validateOnInput: true,
                showErrorsInline: true,
                showProgress: true,
                enableRealTimeValidation: true,
                enableAsyncValidation: true,
                customValidators: this.getEnhancedCustomValidators()
            });
        });
    },

    // Get enhanced custom validators
    getEnhancedCustomValidators: function() {
        const validators = {};
        
        // Enhanced password confirmation validator
        validators['password-confirm'] = (value, element) => {
            const passwordField = document.getElementById(element.dataset.passwordMatch);
            if (!passwordField) return { valid: true, message: '' };
            
            const isValid = value === passwordField.value;
            return {
                valid: isValid,
                message: isValid ? '' : 'Passwords do not match'
            };
        };

        // Enhanced date range validator
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

        // Business hours validator with time zones
        validators['business-hours-tz'] = (value, element) => {
            if (!value) return { valid: true, message: '' };
            
            const timeZone = element.dataset.timeZone || 'local';
            const businessStart = element.dataset.businessStart || '06:00';
            const businessEnd = element.dataset.businessEnd || '23:59';
            
            // Convert to target timezone for validation
            // This would integrate with a timezone library
            const isValid = true; // Simplified for now
            
            return {
                valid: isValid,
                message: isValid ? '' : `Time must be between ${businessStart} and ${businessEnd} ${timeZone}`
            };
        };

        return validators;
    },

    // Setup enhanced input formatting
    setupEnhancedInputFormatting: function() {
        // Enhanced phone number formatting with country code support
        document.querySelectorAll('input[data-format="phone-enhanced"]').forEach(input => {
            input.addEventListener('input', function() {
                let value = input.value.replace(/\D/g, '');
                const countryCode = this.dataset.countryCode || 'IN';
                
                // Format based on country code
                if (countryCode === 'IN') {
                    // Indian format: XXXXX-XXXXX
                    if (value.length <= 5) {
                        input.value = value;
                    } else {
                        input.value = value.slice(0, 5) + '-' + value.slice(5, 10);
                    }
                }
            });
        });

        // Enhanced card number formatting with type detection
        document.querySelectorAll('input[data-format="card-enhanced"]').forEach(input => {
            input.addEventListener('input', function() {
                let value = input.value.replace(/\s/g, '');
                let formattedValue = '';
                
                // Add spaces based on card type
                if (value.length <= 4) {
                    formattedValue = value;
                } else if (value.length <= 8) {
                    formattedValue = value.slice(0, 4) + ' ' + value.slice(4);
                } else if (value.length <= 12) {
                    formattedValue = value.slice(0, 4) + ' ' + value.slice(4, 8) + ' ' + value.slice(8);
                } else {
                    formattedValue = value.slice(0, 4) + ' ' + value.slice(4, 8) + ' ' + value.slice(8, 12) + ' ' + value.slice(12, 16);
                }
                
                input.value = formattedValue;
            });
        });

        // Auto-sanitize all text inputs on blur
        document.querySelectorAll('textarea[data-auto-sanitize="enhanced"], input[data-auto-sanitize="enhanced"]').forEach(element => {
            element.addEventListener('blur', function() {
                this.value = EnhancedSecurityValidator.sanitizeInput(this.value);
            });
        });
    },

    // Show validation summary
    showValidationSummary: function(validator) {
        const state = validator.getValidationState();
        
        if (state.hasErrors || state.hasWarnings) {
            const summary = document.createElement('div');
            summary.className = 'validation-summary alert alert-info';
            summary.innerHTML = `
                <h6><i class="fas fa-info-circle me-2"></i>Validation Summary</h6>
                <div class="row">
                    <div class="col-md-6">
                        <strong>Fields:</strong> ${state.validFields}/${state.totalFields} valid
                    </div>
                    <div class="col-md-6">
                        <strong>Issues:</strong> ${Object.keys(validator.errors).length} errors, ${Object.keys(validator.warnings).length} warnings
                    </div>
                </div>
            `;
            
            const form = validator.form;
            const existingSummary = form.querySelector('.validation-summary');
            if (existingSummary) {
                existingSummary.remove();
            }
            
            form.insertBefore(summary, form.firstChild);
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    EnhancedValidationUtils.initAllForms();
    EnhancedValidationUtils.setupEnhancedInputFormatting();
});

// Export for use in other scripts
window.EnhancedFormValidator = EnhancedFormValidator;
window.EnhancedSecurityValidator = EnhancedSecurityValidator;
window.EnhancedValidationUtils = EnhancedValidationUtils;