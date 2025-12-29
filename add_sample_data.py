#!/usr/bin/env python
"""
Add sample data to the database
"""
from app import create_app
from app.database import db
from app.auth.models import User
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.shows.models import Show
from datetime import date, time, datetime, timedelta

def add_sample_data():
    """Add sample data to the database"""
    app = create_app()
    
    with app.app_context():
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
            
            db.session.commit()
            print("Users created successfully!")
        
        # Check if we have movies
        if Movie.query.count() == 0:
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
            
            db.session.commit()
            print("Movies created successfully!")
        
        # Check if we have screens
        if Screen.query.count() == 0:
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
            print("Screens created successfully!")
        
        # Check if we have shows
        if Show.query.count() == 0:
            movie1 = Movie.query.first()
            screen1 = Screen.query.filter_by(name='Screen 1').first()
            
            if movie1 and screen1:
                # Helper function to calculate end time
                def calculate_end_time(start_time, duration_minutes):
                    start_datetime = datetime.combine(date.today(), start_time)
                    end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                    return end_datetime.time()
                
                # Create a sample show
                show1 = Show(
                    movie_id=movie1.id,
                    screen_id=screen1.id,
                    show_date=date.today(),
                    show_time=time(18, 0),  # 6:00 PM
                    base_price=200.00,
                    end_time=calculate_end_time(time(18, 0), movie1.duration)
                )
                db.session.add(show1)
                db.session.commit()
                print("Sample show created successfully!")

if __name__ == '__main__':
    add_sample_data()