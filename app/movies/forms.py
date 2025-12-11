"""
Movies Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, DateField, URLField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, URL, ValidationError
from datetime import datetime
from app.validators import DataValidators, InputSanitizer, SecurityValidator
from app.movies.models import Movie


class MovieForm(FlaskForm):
    """Movie form for adding and editing movies"""
    name = StringField('Movie Title', validators=[
        DataRequired(message='Movie title is required'),
        Length(min=1, max=100, message='Title must be between 1 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=1000, message='Description cannot exceed 1000 characters')
    ])
    duration = IntegerField('Duration (minutes)', validators=[
        DataRequired(message='Duration is required'),
        NumberRange(min=1, max=600, message='Duration must be between 1 and 600 minutes')
    ])
    genre = SelectField('Genre', choices=[
        ('', 'Select Genre'),
        ('Action', 'Action'),
        ('Comedy', 'Comedy'),
        ('Drama', 'Drama'),
        ('Horror', 'Horror'),
        ('Romance', 'Romance'),
        ('Sci-Fi', 'Sci-Fi'),
        ('Thriller', 'Thriller'),
        ('Animation', 'Animation'),
        ('Documentary', 'Documentary'),
        ('Family', 'Family'),
        ('Fantasy', 'Fantasy'),
        ('Musical', 'Musical'),
        ('Mystery', 'Mystery'),
        ('Western', 'Western')
    ], validators=[DataRequired(message='Please select a genre')])
    release_date = DateField('Release Date', validators=[
        DataRequired(message='Release date is required')
    ])
    poster_url = URLField('Poster URL', validators=[
        Optional(),
        URL(message='Please enter a valid URL')
    ])
    rating = SelectField('Rating', choices=[
        ('', 'Select Rating'),
        ('G', 'G - General Audiences'),
        ('PG', 'PG - Parental Guidance'),
        ('PG-13', 'PG-13 - Parents Strongly Cautioned'),
        ('R', 'R - Restricted'),
        ('NC-17', 'NC-17 - Adults Only')
    ], validators=[DataRequired(message='Please select a rating')])
    language = SelectField('Language', choices=[
        ('English', 'English'),
        ('Hindi', 'Hindi'),
        ('Tamil', 'Tamil'),
        ('Telugu', 'Telugu'),
        ('Malayalam', 'Malayalam'),
        ('Kannada', 'Kannada'),
        ('Bengali', 'Bengali'),
        ('Marathi', 'Marathi'),
        ('Gujarati', 'Gujarati'),
        ('Punjabi', 'Punjabi'),
        ('Other', 'Other')
    ], validators=[DataRequired(message='Please select a language')])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], default='active', validators=[DataRequired(message='Please select a status')])
    submit = SubmitField('Save Movie')
    
    def validate_name(self, field):
        """Validate and sanitize movie name"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            if not sanitized:
                raise ValidationError('Movie title cannot be empty')
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in movie title')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in movie title')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Validate title uniqueness
            # Only check for duplicates when creating a new movie (not editing)
            if hasattr(self, '_obj') and self._obj is None:
                existing_movie = Movie.query.filter_by(name=sanitized).first()
                if existing_movie:
                    raise ValidationError('A movie with this title already exists')
    
    def validate_description(self, field):
        """Validate and sanitize description"""
        if field.data:
            # Sanitize input (allow basic formatting)
            sanitized = InputSanitizer.sanitize_string(
                field.data, 
                allow_tags=['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
                max_length=1000
            )
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in description')
            
            # Update field data with sanitized version
            field.data = sanitized
    
    def validate_poster_url(self, field):
        """Validate and sanitize poster URL"""
        if field.data:
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in URL')
            
            # Additional validation for URL
            if field.data:
                # Check for malicious URLs
                lower_url = field.data.lower()
                if any(malicious in lower_url for malicious in 
                          ['javascript:', 'data:', 'vbscript:', 'file://']):
                    raise ValidationError('Invalid URL format')
    
    def validate_release_date(self, field):
        """Validate that release date is not too far in the future"""
        if field.data:
            today = datetime.now().date()
            # Allow release dates up to 2 years in the future
            max_future_date = today.replace(year=today.year + 2)
            if field.data > max_future_date:
                raise ValidationError('Release date cannot be more than 2 years in the future')
            
            # Don't allow release dates in the distant past
            min_date = today.replace(year=today.year - 100)
            if field.data < min_date:
                raise ValidationError('Release date seems too far in the past')


class MovieSearchForm(FlaskForm):
    """Form for searching movies with enhanced validation"""
    search = StringField('Search', validators=[
        Optional(),
        Length(max=100, message='Search term cannot exceed 100 characters')
    ])
    genre = SelectField('Genre', choices=[
        ('', 'All Genres'),
        ('Action', 'Action'),
        ('Comedy', 'Comedy'),
        ('Drama', 'Drama'),
        ('Horror', 'Horror'),
        ('Romance', 'Romance'),
        ('Sci-Fi', 'Sci-Fi'),
        ('Thriller', 'Thriller'),
        ('Animation', 'Animation'),
        ('Documentary', 'Documentary'),
        ('Family', 'Family'),
        ('Fantasy', 'Fantasy'),
        ('Musical', 'Musical'),
        ('Mystery', 'Mystery'),
        ('Western', 'Western')
    ], validators=[Optional()])
    language = SelectField('Language', choices=[
        ('', 'All Languages'),
        ('English', 'English'),
        ('Hindi', 'Hindi'),
        ('Tamil', 'Tamil'),
        ('Telugu', 'Telugu'),
        ('Malayalam', 'Malayalam'),
        ('Kannada', 'Kannada'),
        ('Bengali', 'Bengali'),
        ('Marathi', 'Marathi'),
        ('Gujarati', 'Gujarati'),
        ('Punjabi', 'Punjabi'),
        ('Other', 'Other')
    ], validators=[Optional()])
    status = SelectField('Status', choices=[
        ('', 'All Status'),
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], validators=[Optional()])
    rating = SelectField('Rating', choices=[
        ('', 'All Ratings'),
        ('G', 'G - General Audiences'),
        ('PG', 'PG - Parental Guidance'),
        ('PG-13', 'PG-13 - Parents Strongly Cautioned'),
        ('R', 'R - Restricted'),
        ('NC-17', 'NC-17 - Adults Only')
    ], validators=[Optional()])
    submit = SubmitField('Search')
    
    def validate_search(self, field):
        """Validate and sanitize search term"""
        if field.data:
            # Sanitize input
            sanitized = InputSanitizer.sanitize_string(field.data, max_length=100)
            
            # Check for SQL injection
            if SecurityValidator.detect_sql_injection(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Check for XSS
            if SecurityValidator.detect_xss(field.data):
                raise ValidationError('Invalid characters detected in search term')
            
            # Update field data with sanitized version
            field.data = sanitized
            
            # Check for empty search after sanitization
            if not sanitized.strip():
                raise ValidationError('Please enter a valid search term')