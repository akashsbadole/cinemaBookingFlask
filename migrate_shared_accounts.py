"""
Database migration script to add shared account support
"""
import sqlite3
import json
import os
from app.database import db
from app.auth.models import User

def migrate_shared_accounts():
    """Migrate existing users to support shared accounts"""
    
    # Get database path
    db_path = os.path.join('instance', 'cinema_pos_dev.db')
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Add new columns if they don't exist
        print("Adding new columns to user table...")
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'assigned_roles' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN assigned_roles TEXT")
            print("[OK] Added assigned_roles column")
        
        if 'is_shared_account' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN is_shared_account BOOLEAN DEFAULT 0")
            print("[OK] Added is_shared_account column")
        
        # Update existing users
        print("Updating existing users...")
        
        # Get all users
        cursor.execute("SELECT id, role FROM user")
        users = cursor.fetchall()
        
        for user_id, role in users:
            # Set default assigned_roles based on current role
            assigned_roles = json.dumps([role])
            
            # Set is_shared_account to False for existing users
            is_shared = 0
            
            cursor.execute(
                "UPDATE user SET assigned_roles = ?, is_shared_account = ? WHERE id = ?",
                (assigned_roles, is_shared, user_id)
            )
        
        conn.commit()
        print(f"[OK] Updated {len(users)} existing users")
        
        # Create a sample shared account for testing
        print("Creating sample shared account...")
        
        # Check if shared account already exists
        cursor.execute("SELECT id FROM user WHERE username = 'shared'")
        existing = cursor.fetchone()
        
        if not existing:
            # Create shared account
            from werkzeug.security import generate_password_hash
            
            cursor.execute("""
                INSERT INTO user (username, email, password_hash, role, assigned_roles, is_shared_account, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                'shared',
                'shared@cinema.com',
                generate_password_hash('SharedPass123!'),
                'admin',
                json.dumps(['admin', 'cashier']),
                1,
                1
            ))
            
            conn.commit()
            print("[OK] Created shared account: username='shared', password='SharedPass123!'")
        else:
            print("[OK] Shared account already exists")
        
        print("[OK] Migration completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Starting shared account migration...")
    migrate_shared_accounts()
    print("Migration finished!")