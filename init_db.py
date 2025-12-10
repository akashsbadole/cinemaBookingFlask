#!/usr/bin/env python
"""
Database initialization script for Cinema POS application
"""
from app import create_app
from app.database import db
from app.auth.models import User
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from datetime import datetime, date, time

def init_database():
    """Initialize the database with tables and sample data"""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")
        
        # Check if admin user exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            # Create admin user
            admin_user = User(
                username='admin',
                email='admin@cinema.com',
                role='admin'
            )
            admin_user.set_password('Admin123!')
            db.session.add(admin_user)
            
            # Create cashier user
            cashier_user = User(
                username='cashier',
                email='cashier@cinema.com',
                role='cashier'
            )
            cashier_user.set_password('Cashier123!')
            db.session.add(cashier_user)
            
            # Create sample screens
            screen1 = Screen(
                name='Screen 1',
                total_rows=8,
                total_columns=10
            )
            db.session.add(screen1)
            
            screen2 = Screen(
                name='Screen 2',
                total_rows=6,
                total_columns=8
            )
            db.session.add(screen2)
            
            db.session.commit()
            
            # Create seats for screen 1
            for row in range(1, screen1.total_rows + 1):
                row_letter = chr(64 + row)  # A, B, C, etc.
                for col in range(1, screen1.total_columns + 1):
                    seat_type = 'normal'
                    price = 150.00
                    
                    # Make premium seats in middle rows
                    if 3 <= row <= 6:
                        seat_type = 'premium'
                        price = 200.00
                    
                    # Make VIP seats in last row
                    if row == screen1.total_rows:
                        seat_type = 'vip'
                        price = 300.00
                    
                    seat = Seat(
                        screen_id=screen1.id,
                        row=row_letter,
                        column=col,
                        type=seat_type,
                        price=price
                    )
                    db.session.add(seat)
            
            # Create seats for screen 2
            for row in range(1, screen2.total_rows + 1):
                row_letter = chr(64 + row)  # A, B, C, etc.
                for col in range(1, screen2.total_columns + 1):
                    seat_type = 'normal'
                    price = 120.00
                    
                    # Make premium seats in middle rows
                    if 2 <= row <= 5:
                        seat_type = 'premium'
                        price = 180.00
                    
                    # Make VIP seats in last row
                    if row == screen2.total_rows:
                        seat_type = 'vip'
                        price = 250.00
                    
                    seat = Seat(
                        screen_id=screen2.id,
                        row=row_letter,
                        column=col,
                        type=seat_type,
                        price=price
                    )
                    db.session.add(seat)
            
            # Create sample movies
            movie1 = Movie(
                name='Avengers: Endgame',
                duration=181,
                language='English',
                status='active'
            )
            db.session.add(movie1)
            
            movie2 = Movie(
                name='Dangal',
                duration=161,
                language='Hindi',
                status='active'
            )
            db.session.add(movie2)
            
            movie3 = Movie(
                name='Spider-Man: No Way Home',
                duration=148,
                language='English',
                status='active'
            )
            db.session.add(movie3)
            
            db.session.commit()
            
            # Create sample shows for today and tomorrow
            today = date.today()
            tomorrow = date.today()
            
            # Shows for today
            show1 = Show(
                movie_id=movie1.id,
                screen_id=screen1.id,
                show_date=today,
                show_time=time(10, 0),  # 10:00 AM
                base_price=180.00
            )
            db.session.add(show1)
            
            show2 = Show(
                movie_id=movie1.id,
                screen_id=screen1.id,
                show_date=today,
                show_time=time(14, 30),  # 2:30 PM
                base_price=200.00
            )
            db.session.add(show2)
            
            show3 = Show(
                movie_id=movie2.id,
                screen_id=screen2.id,
                show_date=today,
                show_time=time(11, 0),  # 11:00 AM
                base_price=150.00
            )
            db.session.add(show3)
            
            show4 = Show(
                movie_id=movie3.id,
                screen_id=screen1.id,
                show_date=tomorrow,
                show_time=time(18, 0),  # 6:00 PM
                base_price=220.00
            )
            db.session.add(show4)
            
            db.session.commit()
            
            print("Sample data created successfully!")
            print("Admin user: admin / Admin123!")
            print("Cashier user: cashier / Cashier123!")
        else:
            print("Database already initialized!")

if __name__ == '__main__':
    init_database()