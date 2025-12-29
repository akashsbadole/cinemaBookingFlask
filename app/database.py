"""
Database initialization and validation
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, inspect
import logging

db = SQLAlchemy()

def validate_database_schema():
    """
    Validate database schema to ensure all required tables and columns exist
    Returns a dictionary with validation results
    """
    validation_results = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'missing_tables': [],
        'missing_columns': {}
    }
    
    try:
        # Required tables and their essential columns
        required_schema = {
            'user': ['id', 'username', 'email', 'password_hash', 'role'],
            'movie': ['id', 'title', 'genre', 'language', 'duration', 'rating', 'status'],
            'screen': ['id', 'name', 'total_rows', 'total_columns', 'status'],
            'seat': ['id', 'screen_id', 'row', 'column', 'seat_number', 'type', 'price', 'status'],
            'show': ['id', 'movie_id', 'screen_id', 'show_date', 'show_time', 'base_price', 'status'],
            'booking': ['id', 'reference_number', 'customer_name', 'customer_email', 'customer_phone', 'total_amount', 'status', 'booking_time'],
            'booking_seat': ['id', 'booking_id', 'seat_id', 'status', 'price'],
            'payment': ['id', 'booking_id', 'amount', 'mode', 'status', 'payment_date']
        }
        
        # Get database inspector
        inspector = inspect(db.engine)
        
        # Check if tables exist
        existing_tables = inspector.get_table_names()
        
        for table_name in required_schema:
            if table_name not in existing_tables:
                validation_results['missing_tables'].append(table_name)
                validation_results['errors'].append(f"Missing required table: {table_name}")
                validation_results['is_valid'] = False
                continue
            
            # Check if columns exist for existing tables
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            required_columns = required_schema[table_name]
            
            missing_columns = []
            for column in required_columns:
                if column not in existing_columns:
                    missing_columns.append(column)
            
            if missing_columns:
                validation_results['missing_columns'][table_name] = missing_columns
                validation_results['errors'].append(f"Table '{table_name}' is missing columns: {', '.join(missing_columns)}")
                validation_results['is_valid'] = False
        
        # Additional validation checks
        try:
            # Test basic connectivity
            db.session.execute(text('SELECT 1'))
        except Exception as e:
            validation_results['errors'].append(f"Database connectivity test failed: {str(e)}")
            validation_results['is_valid'] = False
        
        # Check for foreign key constraints
        try:
            foreign_keys = inspector.get_foreign_keys()
            expected_foreign_keys = {
                'seat': ['screen_id'],
                'show': ['movie_id', 'screen_id'],
                'booking': ['user_id', 'show_id'],
                'booking_seat': ['booking_id', 'seat_id'],
                'payment': ['booking_id']
            }
            
            for table_name, expected_fks in expected_foreign_keys.items():
                if table_name in existing_tables:
                    table_fks = [fk['constrained_columns'] for fk in foreign_keys if fk['referred_table'] == table_name]
                    # This is a simplified check - in practice, you'd need more sophisticated FK validation
        except Exception as e:
            validation_results['warnings'].append(f"Foreign key validation warning: {str(e)}")
        
    except Exception as e:
        validation_results['errors'].append(f"Schema validation error: {str(e)}")
        validation_results['is_valid'] = False
        logging.error(f"Database schema validation failed: {str(e)}")
    
    return validation_results

def fix_database_schema():
    """
    Attempt to fix common database schema issues
    Returns a dictionary with fix results
    """
    fix_results = {
        'success': False,
        'actions_taken': [],
        'errors': []
    }
    
    try:
        # This function would contain logic to create missing tables/columns
        # For now, it just logs the need for manual intervention
        validation = validate_database_schema()
        
        if validation['missing_tables']:
            fix_results['errors'].append(f"Missing tables require manual creation: {', '.join(validation['missing_tables'])}")
        
        if validation['missing_columns']:
            for table, columns in validation['missing_columns'].items():
                fix_results['errors'].append(f"Table '{table}' missing columns: {', '.join(columns)}")
        
        fix_results['success'] = len(fix_results['errors']) == 0
        
    except Exception as e:
        fix_results['errors'].append(f"Schema fix error: {str(e)}")
        logging.error(f"Database schema fix failed: {str(e)}")
    
    return fix_results

def get_database_info():
    """
    Get general database information
    Returns a dictionary with database metadata
    """
    info = {
        'tables': [],
        'total_records': {},
        'database_size': None
    }
    
    try:
        inspector = inspect(db.engine)
        info['tables'] = inspector.get_table_names()
        
        # Get record counts for main tables
        main_tables = ['user', 'movie', 'screen', 'seat', 'show', 'booking', 'payment']
        for table in main_tables:
            if table in info['tables']:
                try:
                    result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    info['total_records'][table] = result.scalar()
                except Exception:
                    info['total_records'][table] = 'Error'
        
        # Get database size (SQLite specific)
        try:
            result = db.session.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"))
            info['database_size'] = result.scalar()
        except Exception:
            info['database_size'] = 'Unknown'
            
    except Exception as e:
        logging.error(f"Failed to get database info: {str(e)}")
        info['error'] = str(e)
    
    return info