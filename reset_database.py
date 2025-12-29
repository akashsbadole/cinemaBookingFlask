#!/usr/bin/env python
"""
Database reset script to force recreate all tables
"""
from app import create_app
from app.database import db

def reset_database():
    """Force recreate all database tables"""
    app = create_app()
    
    with app.app_context():
        # Drop all tables
        print("Dropping all tables...")
        db.drop_all()
        
        # Create all tables
        print("Creating all tables...")
        db.create_all()
        
        print("Database reset completed successfully!")

if __name__ == '__main__':
    reset_database()