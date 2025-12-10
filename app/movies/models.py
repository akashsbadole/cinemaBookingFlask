"""
Movies Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Movie(db.Model):
    """Movie model"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    language = db.Column(db.String(20), nullable=False)
    status = db.Column(db.Enum('active', 'inactive', name='movie_status'), default='active', nullable=False)
    
    # Relationships
    shows = db.relationship('Show', backref='movie', lazy=True)
    
    def __repr__(self):
        return f'<Movie {self.name}>'