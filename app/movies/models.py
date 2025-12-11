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
    description = db.Column(db.Text)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    genre = db.Column(db.String(50))
    release_date = db.Column(db.Date)
    poster_url = db.Column(db.String(255))  # URL to poster image
    rating = db.Column(db.String(10))  # MPAA rating
    language = db.Column(db.String(20), nullable=False)
    status = db.Column(db.Enum('active', 'inactive', name='movie_status'), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    shows = db.relationship('Show', backref='movie', lazy=True)
    
    def __repr__(self):
        return f'<Movie {self.name}>'
    
    def to_dict(self):
        """Convert movie to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'duration': self.duration,
            'genre': self.genre,
            'release_date': self.release_date.isoformat() if self.release_date else None,
            'poster_url': self.poster_url,
            'rating': self.rating,
            'language': self.language,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }