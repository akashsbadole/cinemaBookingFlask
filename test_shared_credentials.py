"""
Test script for shared credential functionality
"""
import os
import sys
import tempfile
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Add the app to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.auth.models import User

def test_shared_credentials():
    """Test the shared credential system"""
    
    # Create app with test config
    app = create_app('development')
    
    with app.app_context():
        try:
            print("Testing Shared Credential System")
            print("=" * 40)
            
            # Test 1: Check if shared account was created
            print("Test 1: Checking shared account creation...")
            shared_user = User.query.filter_by(username='shared').first()
            if shared_user:
                print(f"[OK] Found shared account: {shared_user.username}")
                print(f"    - Email: {shared_user.email}")
                print(f"    - Is shared: {shared_user.is_shared_account_user()}")
                print(f"    - Assigned roles: {shared_user.get_assigned_roles()}")
                print(f"    - Has admin role: {shared_user.has_role('admin')}")
                print(f"    - Has cashier role: {shared_user.has_role('cashier')}")
                
                # Test password
                if shared_user.check_password('SharedPass123!'):
                    print("[OK] Password verification works")
                else:
                    print("[ERROR] Password verification failed")
            else:
                print("[ERROR] Shared account not found")
            
            # Test 2: Check existing users
            print("\nTest 2: Checking existing users...")
            all_users = User.query.all()
            for user in all_users:
                print(f"    - {user.username} ({user.role}): shared={user.is_shared_account_user()}, roles={user.get_assigned_roles()}")
            
            # Test 3: Create a new shared account programmatically
            print("\nTest 3: Creating new shared account...")
            new_shared = User(
                username='testshared',
                email='testshared@example.com',
                role='admin',
                is_shared_account=True
            )
            new_shared.set_password('TestPass123!')
            new_shared.set_assigned_roles(['admin', 'cashier'])
            
            db.session.add(new_shared)
            db.session.commit()
            
            print(f"[OK] Created new shared account: {new_shared.username}")
            print(f"    - Has admin role: {new_shared.has_role('admin')}")
            print(f"    - Has cashier role: {new_shared.has_role('cashier')}")
            
            # Test 4: Role switching simulation
            print("\nTest 4: Testing role switching simulation...")
            from flask import session
            
            with app.test_request_context():
                # Simulate login and role selection
                session['current_role'] = 'admin'
                print(f"[OK] Set session role to admin")
                
                # Test role checking with session
                if new_shared.is_admin():
                    print("[OK] is_admin() returns True when session role is admin")
                else:
                    print("[ERROR] is_admin() failed with session role admin")
                
                # Switch to cashier role
                session['current_role'] = 'cashier'
                print(f"[OK] Switched session role to cashier")
                
                if new_shared.is_cashier():
                    print("[OK] is_cashier() returns True when session role is cashier")
                else:
                    print("[ERROR] is_cashier() failed with session role cashier")
            
            print("\n[SUCCESS] All shared credential tests completed!")
            
        except Exception as e:
            print(f"[ERROR] Test failed: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_shared_credentials()