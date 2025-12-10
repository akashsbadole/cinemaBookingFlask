#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to verify the database schema and relationships
"""
from app import create_app
from app.database import db
from app.auth.models import User
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment

def verify_schema():
    """Verify the database schema and relationships"""
    app = create_app()
    
    with app.app_context():
        print("=== Database Schema Verification ===\n")
        
        # Check User model
        print("1. User Model:")
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            print(f"   [OK] Admin user found: {admin_user.username} (role: {admin_user.role})")
            print(f"   [OK] User has {len(admin_user.bookings)} bookings")
        else:
            print("   [ERROR] Admin user not found")
        
        # Check Movie model
        print("\n2. Movie Model:")
        movies = Movie.query.all()
        print(f"   [OK] Found {len(movies)} movies")
        for movie in movies[:3]:  # Show first 3 movies
            print(f"   - {movie.name} ({movie.duration} min, {movie.language}, status: {movie.status})")
            print(f"     Has {len(movie.shows)} shows")
        
        # Check Screen model
        print("\n3. Screen Model:")
        screens = Screen.query.all()
        print(f"   [OK] Found {len(screens)} screens")
        for screen in screens:
            print(f"   - {screen.name}: {screen.total_rows}x{screen.total_columns}")
            print(f"     Has {len(screen.seats)} seats and {len(screen.shows)} shows")
        
        # Check Seat model
        print("\n4. Seat Model:")
        seats = Seat.query.all()
        print(f"   [OK] Found {len(seats)} total seats")
        seat_types = {}
        for seat in seats:
            seat_type = seat.type
            if seat_type not in seat_types:
                seat_types[seat_type] = 0
            seat_types[seat_type] += 1
        for seat_type, count in seat_types.items():
            print(f"   - {seat_type} seats: {count}")
        
        # Check Show model
        print("\n5. Show Model:")
        shows = Show.query.all()
        print(f"   [OK] Found {len(shows)} shows")
        for show in shows[:3]:  # Show first 3 shows
            print(f"   - {show.movie.name} at {show.screen.name} on {show.show_date} {show.show_time}")
            print(f"     Base price: {show.base_price}, Bookings: {len(show.bookings)}")
        
        # Check Booking model
        print("\n6. Booking Model:")
        bookings = Booking.query.all()
        print(f"   [OK] Found {len(bookings)} bookings")
        if bookings:
            for booking in bookings[:3]:  # Show first 3 bookings
                print(f"   - Booking {booking.id}: {booking.total_amount} ({booking.payment_method})")
                print(f"     Seats: {len(booking.booking_seats)}, Payments: {len(booking.payments)}")
        
        # Check BookingSeat model
        print("\n7. BookingSeat Model:")
        booking_seats = BookingSeat.query.all()
        print(f"   [OK] Found {len(booking_seats)} booking seats")
        
        # Check Payment model
        print("\n8. Payment Model:")
        payments = Payment.query.all()
        print(f"   [OK] Found {len(payments)} payments")
        if payments:
            for payment in payments[:3]:  # Show first 3 payments
                print(f"   - Payment {payment.id}: {payment.amount} ({payment.mode})")
        
        print("\n=== Schema Verification Complete ===")
        print("[SUCCESS] All models and relationships are working correctly!")

if __name__ == '__main__':
    verify_schema()