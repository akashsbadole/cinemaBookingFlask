#!/usr/bin/env python3
"""
Debug script to test API endpoints and identify issues
"""
import os
import sys
import json
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Set Flask environment
os.environ['FLASK_ENV'] = 'development'
os.environ['DATABASE_URL'] = 'sqlite:///instance/cinema_pos_dev.db'

from app import create_app
from app.database import db
from app.models import User, Movie, Show, Screen, Seat

def test_api_endpoints():
    """Test the problematic API endpoints"""
    
    print("=== API Endpoint Debugging ===")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Initialize database
        db.create_all()
        
        # Create a test user
        print("\n1. Creating test user...")
        test_user = User(
            username='testuser',
            email='test@example.com',
            role='cashier'
        )
        test_user.set_password('TestPass123')
        db.session.add(test_user)
        db.session.commit()
        print(f"   ✓ Test user created with ID: {test_user.id}")
        
        # Create test data
        print("\n2. Creating test data...")
        
        # Create a movie
        movie = Movie(
            title='Test Movie',
            description='Test description',
            duration_minutes=120,
            genre='Action',
            rating='PG-13',
            status='active'
        )
        db.session.add(movie)
        db.session.flush()
        print(f"   ✓ Movie created with ID: {movie.id}")
        
        # Create a screen
        screen = Screen(
            name='Test Screen',
            total_rows=5,
            total_columns=10
        )
        db.session.add(screen)
        db.session.commit()
        print(f"   ✓ Screen created with ID: {screen.id}")
        
        # Generate seats for the screen
        screen.generate_seats(pattern='regular', normal_price=150.0)
        db.session.commit()
        print(f"   ✓ Generated {len(screen.seats)} seats")
        
        # Create a show
        show = Show(
            movie_id=movie.id,
            screen_id=screen.id,
            show_date=datetime.now().date(),
            show_time=datetime.now().time(),
            base_price=150.00,
            status='scheduled'
        )
        db.session.add(show)
        db.session.commit()
        print(f"   ✓ Show created with ID: {show.id}")
        
        # Test the API endpoints
        print("\n3. Testing API endpoints...")
        
        with app.test_client() as client:
            # Login the test user first
            print("   → Logging in test user...")
            login_response = client.post('/auth/login', data={
                'username': 'testuser',
                'password': 'testpass'
            }, follow_redirects=True)
            print(f"   Login response: {login_response.status_code}")
            
            # Test lock_seats endpoint
            print("\n4. Testing lock_seats endpoint...")
            lock_data = {
                'show_id': show.id,
                'seat_ids': [screen.seats[0].id],  # First seat
                'duration_minutes': 5
            }
            
            print(f"   Request data: {lock_data}")
            
            lock_response = client.post('/bookings/api/lock_seats',
                                      json=lock_data,
                                      headers={'Content-Type': 'application/json'})
            
            print(f"   Response status: {lock_response.status_code}")
            print(f"   Response data: {lock_response.get_data(as_text=True)}")
            
            # Test release_seats endpoint
            print("\n5. Testing release_seats endpoint...")
            release_data = {
                'show_id': show.id,
                'seat_ids': [screen.seats[0].id]
            }
            
            print(f"   Request data: {release_data}")
            
            release_response = client.post('/bookings/api/release_seats',
                                         json=release_data,
                                         headers={'Content-Type': 'application/json'})
            
            print(f"   Response status: {release_response.status_code}")
            print(f"   Response data: {release_response.get_data(as_text=True)}")
            
            # Test seat_status endpoint
            print("\n6. Testing seat_status endpoint...")
            status_response = client.get(f'/bookings/api/show/{show.id}/seat_status')
            
            print(f"   Response status: {status_response.status_code}")
            print(f"   Response data: {status_response.get_data(as_text=True)}")
        
        print("\n=== Test completed ===")

if __name__ == '__main__':
    try:
        test_api_endpoints()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()