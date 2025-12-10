#!/usr/bin/env python
"""
Test script for authentication system
"""
import requests
from bs4 import BeautifulSoup

BASE_URL = 'http://127.0.0.1:5000'

def get_csrf_token(session, url):
    """Extract CSRF token from form"""
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    return csrf_input['value'] if csrf_input else None

def test_admin_login():
    """Test admin login"""
    session = requests.Session()
    
    # Get login page and CSRF token
    csrf_token = get_csrf_token(session, f'{BASE_URL}/auth/login')
    print(f"CSRF Token: {csrf_token}")
    
    # Login with admin credentials
    login_data = {
        'username': 'admin',
        'password': 'Admin123!',
        'remember_me': False,
        'csrf_token': csrf_token
    }
    
    response = session.post(f'{BASE_URL}/auth/login', data=login_data)
    
    if response.status_code == 200 and 'Dashboard' in response.text:
        print("[SUCCESS] Admin login successful!")
        
        # Test dashboard access
        dashboard_response = session.get(f'{BASE_URL}/')
        if dashboard_response.status_code == 200:
            print("[SUCCESS] Admin dashboard access successful!")
            
            # Test admin-only features
            register_response = session.get(f'{BASE_URL}/auth/register')
            if register_response.status_code == 200:
                print("[SUCCESS] Admin can access registration page!")
            else:
                print("[FAIL] Admin cannot access registration page")
        else:
            print("[FAIL] Admin dashboard access failed")
    else:
        print("[FAIL] Admin login failed")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}...")
    
    return session

def test_cashier_login():
    """Test cashier login"""
    session = requests.Session()
    
    # Get login page and CSRF token
    csrf_token = get_csrf_token(session, f'{BASE_URL}/auth/login')
    
    # Login with cashier credentials
    login_data = {
        'username': 'cashier',
        'password': 'Cashier123!',
        'remember_me': False,
        'csrf_token': csrf_token
    }
    
    response = session.post(f'{BASE_URL}/auth/login', data=login_data)
    
    if response.status_code == 200 and 'Dashboard' in response.text:
        print("[SUCCESS] Cashier login successful!")
        
        # Test dashboard access
        dashboard_response = session.get(f'{BASE_URL}/')
        if dashboard_response.status_code == 200:
            print("[SUCCESS] Cashier dashboard access successful!")
            
            # Test admin-only features (should fail)
            register_response = session.get(f'{BASE_URL}/auth/register')
            # Check if redirected to login page (302) or forbidden (403)
            if register_response.status_code in [302, 403]:
                print("[SUCCESS] Cashier correctly blocked from admin-only registration page!")
            else:
                print(f"[FAIL] Cashier can access admin-only features (status: {register_response.status_code})")
        else:
            print("[FAIL] Cashier dashboard access failed")
    else:
        print("[FAIL] Cashier login failed")
        print(f"Status: {response.status_code}")
    
    return session

def test_profile_access(session):
    """Test profile access"""
    profile_response = session.get(f'{BASE_URL}/auth/profile')
    if profile_response.status_code == 200:
        print("[SUCCESS] Profile page accessible!")
    else:
        print("[FAIL] Profile page not accessible")

if __name__ == '__main__':
    print("Testing Authentication System")
    print("=" * 40)
    
    print("\n1. Testing Admin Login:")
    admin_session = test_admin_login()
    if admin_session:
        test_profile_access(admin_session)
    
    print("\n2. Testing Cashier Login:")
    cashier_session = test_cashier_login()
    if cashier_session:
        test_profile_access(cashier_session)
    
    print("\n3. Testing Rate Limiting:")
    # Test rate limiting with wrong password
    session = requests.Session()
    for i in range(6):
        csrf_token = get_csrf_token(session, f'{BASE_URL}/auth/login')
        login_data = {
            'username': 'admin',
            'password': 'wrongpassword',
            'remember_me': False,
            'csrf_token': csrf_token
        }
        response = session.post(f'{BASE_URL}/auth/login', data=login_data)
        print(f"Attempt {i+1}: Status {response.status_code}")
        
        if 'Too many failed login attempts' in response.text:
            print("[SUCCESS] Rate limiting is working!")
            break
    
    print("\nAuthentication testing complete!")