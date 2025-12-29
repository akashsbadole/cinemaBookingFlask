# Shared Credentials Implementation Guide

## Overview

This implementation adds shared credential support to the Cinema Management System, allowing both admin and cashier roles to use the same username/password combination. After login, users select their role for the current session.

## Features Implemented

### 1. Database Schema Changes
- **New Columns Added:**
  - `assigned_roles` (TEXT): JSON array of assigned roles for shared accounts
  - `is_shared_account` (BOOLEAN): Flag indicating if account is shared

### 2. User Model Enhancements
- **New Methods:**
  - `has_role(role)`: Check if user has specific role (works for both shared and individual accounts)
  - `get_assigned_roles()`: Get list of assigned roles for shared accounts
  - `set_assigned_roles(roles)`: Set assigned roles for shared accounts
  - `is_shared_account_user()`: Check if this is a shared account
- **Enhanced Methods:**
  - `is_admin()` and `is_cashier()`: Now check session role for shared accounts

### 3. Authentication Flow
1. **Login**: User logs in with shared credentials
2. **Role Selection**: If shared account, redirect to role selection page
3. **Session Management**: Store selected role in session
4. **Access Control**: Use session role for permission checks

### 4. User Interface
- **Registration Form**: Added "Shared Account" checkbox
- **Role Selection Page**: New template for choosing role after shared login
- **Updated Registration**: Support for creating shared accounts

### 5. Security Features
- **Session-based Role Switching**: Role stored in secure session
- **Access Logging**: All role selections logged for audit
- **Role Validation**: Only assigned roles can be selected

## Usage

### Creating Shared Accounts
1. Admin navigates to User Registration
2. Fills in username, email, password
3. Selects "Shared Account" checkbox
4. Account created with both admin and cashier roles

### Using Shared Accounts
1. User logs in with shared username/password
2. System redirects to role selection page
3. User selects desired role (admin or cashier)
4. Session stores selected role for permission checks

### Sample Shared Account
- **Username**: `shared`
- **Password**: `SharedPass123!`
- **Roles**: Both admin and cashier

## API Changes

### User Model
```python
# Check if user is shared account
user.is_shared_account_user()

# Get assigned roles
user.get_assigned_roles()  # Returns ['admin', 'cashier']

# Check specific role
user.has_role('admin')  # True for shared accounts with admin role

# Set roles for shared account
user.set_assigned_roles(['admin', 'cashier'])
```

### Session Management
```python
from flask import session

# Set current role for shared account
session['current_role'] = 'admin'

# Check current role
current_role = session.get('current_role')
```

## Migration

Run the migration script to update existing databases:
```bash
python migrate_shared_accounts.py
```

This script:
- Adds new columns to existing user table
- Updates existing users with default values
- Creates sample shared account for testing

## Testing

Run the test script to validate functionality:
```bash
python test_shared_credentials.py
```

Tests verify:
- Shared account creation
- Role assignment
- Password verification
- Session-based role switching
- Access control methods

## Benefits

1. **Simplified Access Management**: Single username/password for both roles
2. **Flexible Role Switching**: Change roles during same session
3. **Audit Trail**: All role selections logged
4. **Security Maintained**: Session-based permissions
5. **Backward Compatibility**: Existing users unaffected

## Files Modified

### Core Implementation
- `app/auth/models.py`: Enhanced User model with shared account support
- `app/auth/forms.py`: Added RoleSelectionForm and shared account checkbox
- `app/auth/routes.py`: Updated authentication flow and added role selection route

### Templates
- `templates/auth/select_role.html`: New role selection interface
- `templates/auth/register.html`: Updated registration with shared account option

### Utilities
- `migrate_shared_accounts.py`: Database migration script
- `test_shared_credentials.py`: Comprehensive test suite

## Security Considerations

1. **Session Security**: Role stored in secure session, cleared on logout
2. **Access Logging**: All authentication events logged for audit
3. **Role Validation**: Only assigned roles can be selected
4. **Password Security**: Existing password requirements maintained

## Future Enhancements

Potential improvements:
1. **Role Switch Interface**: Allow changing roles during active session
2. **Time-based Roles**: Temporary role assignments
3. **Role History**: Track role changes over time
4. **Bulk Role Management**: Assign roles to multiple users
5. **Advanced Permissions**: Granular permission system