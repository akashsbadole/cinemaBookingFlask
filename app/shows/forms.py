"""
Shows Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SelectField, DateField, TimeField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError
from wtforms.widgets import TextInput
from datetime import datetime, time


class ShowForm(FlaskForm):
    """Show form for adding and editing shows"""
    movie_id = SelectField('Movie', coerce=int, validators=[DataRequired()])
    screen_id = SelectField('Screen', coerce=int, validators=[DataRequired()])
    show_date = DateField('Show Date', validators=[DataRequired()], format='%Y-%m-%d')
    show_time = TimeField('Show Time', validators=[DataRequired()])
    base_price = DecimalField('Base Price', validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be positive')
    ], places=2)
    weekend_surcharge = DecimalField('Weekend Surcharge', default=0.00, validators=[
        NumberRange(min=0, message='Surcharge must be non-negative')
    ], places=2)
    matinee_discount = DecimalField('Matinee Discount', default=0.00, validators=[
        NumberRange(min=0, message='Discount must be non-negative')
    ], places=2)
    show_type = SelectField('Show Type', choices=[
        ('regular', 'Regular'),
        ('matinee', 'Matinee'),
        ('evening', 'Evening'),
        ('night', 'Night')
    ], default='regular')
    submit = SubmitField('Save Show')
    
    def __init__(self, *args, **kwargs):
        super(ShowForm, self).__init__(*args, **kwargs)
        # Populate movie choices
        from app.movies.models import Movie
        self.movie_id.choices = [(m.id, m.name) for m in Movie.query.filter_by(status='active').order_by(Movie.name).all()]
        
        # Populate screen choices
        from app.screens.models import Screen
        self.screen_id.choices = [(s.id, s.name) for s in Screen.query.order_by(Screen.name).all()]
    
    def validate_show_date(self, field):
        """Validate that show date is not in the past"""
        if field.data and field.data < datetime.now().date():
            raise ValidationError('Show date cannot be in the past')
    
    def validate_show_time(self, field):
        """Validate show time is within business hours"""
        if field.data:
            hour = field.data.hour
            if hour < 6 or hour > 23:
                raise ValidationError('Show time must be between 6:00 AM and 11:59 PM')
    
    def validate_base_price(self, field):
        """Validate minimum price"""
        if field.data and field.data < 50:
            raise ValidationError('Base price must be at least ₹50')