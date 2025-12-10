# Cinema POS Database Schema Implementation

## Overview
This document describes the complete database schema implementation for the Cinema POS application according to the specifications in todo.md.

## Implemented Models

### 1. Users Model (app/auth/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `username` (VARCHAR, unique, nullable=False)
  - `password_hash` (VARCHAR, nullable=False)
  - `role` (ENUM: admin, cashier, nullable=False)
- **Relationships:**
  - One-to-many with Bookings (user.bookings)
- **Methods:**
  - `set_password(password)` - Hashes and sets password
  - `check_password(password)` - Verifies password against hash

### 2. Movies Model (app/movies/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `name` (VARCHAR, nullable=False)
  - `duration` (INT, nullable=False) - in minutes
  - `language` (VARCHAR, nullable=False)
  - `status` (ENUM: active, inactive, nullable=False)
- **Relationships:**
  - One-to-many with Shows (movie.shows)

### 3. Screens Model (app/screens/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `name` (VARCHAR, nullable=False)
  - `total_rows` (INT, nullable=False)
  - `total_columns` (INT, nullable=False)
- **Relationships:**
  - One-to-many with Seats (screen.seats)
  - One-to-many with Shows (screen.shows)

### 4. Shows Model (app/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `movie_id` (Foreign key to Movies, nullable=False)
  - `screen_id` (Foreign key to Screens, nullable=False)
  - `show_date` (DATE, nullable=False)
  - `show_time` (TIME, nullable=False)
  - `base_price` (DECIMAL(10,2), nullable=False)
- **Relationships:**
  - Many-to-one with Movies (show.movie)
  - Many-to-one with Screens (show.screen)
  - One-to-many with Bookings (show.bookings)

### 5. Seats Model (app/screens/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `screen_id` (Foreign key to Screens, nullable=False)
  - `row` (VARCHAR, nullable=False) - e.g., 'A', 'B', 'C'
  - `column` (INT, nullable=False)
  - `type` (ENUM: normal, premium, vip, nullable=False)
  - `price` (DECIMAL(10,2), nullable=False)
- **Constraints:**
  - Unique constraint on (screen_id, row, column)
- **Relationships:**
  - Many-to-one with Screens (seat.screen)
  - One-to-many with BookingSeats (seat.booking_seats)

### 6. Bookings Model (app/bookings/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `show_id` (Foreign key to Shows, nullable=False)
  - `user_id` (Foreign key to Users, nullable=False)
  - `booking_time` (DATETIME, nullable=False)
  - `total_amount` (DECIMAL(10,2), nullable=False)
  - `payment_method` (ENUM: cash, card, upi, nullable=False)
  - `customer_name` (VARCHAR, optional)
- **Relationships:**
  - Many-to-one with Shows (booking.show)
  - Many-to-one with Users (booking.user)
  - One-to-many with BookingSeats (booking.booking_seats)
  - One-to-many with Payments (booking.payments)

### 7. BookingSeats Model (app/bookings/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `booking_id` (Foreign key to Bookings, nullable=False)
  - `seat_id` (Foreign key to Seats, nullable=False)
  - `status` (ENUM: booked, locked, nullable=False)
- **Relationships:**
  - Many-to-one with Bookings (booking_seat.booking)
  - Many-to-one with Seats (booking_seat.seat)

### 8. Payments Model (app/payments/models.py)
- **Fields:**
  - `id` (INT, Primary key)
  - `booking_id` (Foreign key to Bookings, nullable=False)
  - `amount` (DECIMAL(10,2), nullable=False)
  - `mode` (ENUM: cash, card, upi, nullable=False)
  - `reference_id` (VARCHAR, optional)
- **Relationships:**
  - Many-to-one with Bookings (payment.booking)

## Database Initialization

The database can be initialized using the `init_db.py` script, which:
1. Creates all tables according to the schema
2. Creates sample users (admin/cashier)
3. Creates sample screens with seats
4. Creates sample movies
5. Creates sample shows
6. Populates the database with initial data

## Schema Verification

The `verify_schema.py` script can be used to verify:
1. All models are properly created
2. Relationships are working correctly
3. Sample data is properly populated
4. All constraints are enforced

## Key Features

1. **Proper Relationships:** All models have correctly defined relationships with appropriate back references
2. **Constraints:** Unique constraints ensure data integrity (e.g., unique seat locations within a screen)
3. **Data Types:** Appropriate data types used for all fields (DECIMAL for monetary values)
4. **Enums:** Used for status fields to ensure data consistency
5. **Nullable Fields:** Properly defined nullable/non-nullable fields
6. **Helper Methods:** User model includes password hashing and verification methods

## Sample Data

The initialization script creates:
- 2 users (admin, cashier)
- 2 screens (Screen 1: 8x10, Screen 2: 6x8)
- 128 total seats with different types (normal, premium, vip)
- 3 movies with different languages and durations
- 4 shows with different dates and times

The database is now ready for the Cinema POS application to use.