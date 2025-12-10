import os
from app import create_app
from app.database import db
from app.auth.models import User

app = create_app(os.getenv('FLASK_CONFIG') or 'default')

@app.shell_context_processor
def make_shell_context():
    """Make database objects available in shell context"""
    return dict(db=db, User=User)

def create_tables():
    """Create database tables and default data"""
    with app.app_context():
        db.create_all()
        
        # Create default admin user if it doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@cinema.com',
                role='admin'
            )
            admin.set_password('Admin123!')
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created: username=admin, password=Admin123!")

if __name__ == '__main__':
    create_tables()
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=app.config.get('DEBUG', False)
    )