"""
Report Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, SubmitField, RadioField
from wtforms.validators import DataRequired, Optional
from app.models import Movie, Screen, User
from app.database import db

class DateRangeForm(FlaskForm):
    """Form for date range selection"""
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField('Generate Report')

class DailySalesForm(FlaskForm):
    """Form for daily sales report filters"""
    report_date = DateField('Report Date', validators=[DataRequired()], format='%Y-%m-%d')
    screen_id = SelectField('Screen', coerce=int, validators=[Optional()])
    movie_id = SelectField('Movie', coerce=int, validators=[Optional()])
    submit = SubmitField('Filter Report')
    
    def __init__(self, *args, **kwargs):
        super(DailySalesForm, self).__init__(*args, **kwargs)
        self.screen_id.choices = [(0, 'All Screens')] + [(s.id, s.name) for s in Screen.query.all()]
        self.movie_id.choices = [(0, 'All Movies')] + [(m.id, m.title) for m in Movie.query.filter_by(status='active').all()]

class OccupancyForm(FlaskForm):
    """Form for occupancy report filters"""
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    screen_id = SelectField('Screen', coerce=int, validators=[Optional()])
    movie_id = SelectField('Movie', coerce=int, validators=[Optional()])
    submit = SubmitField('Filter Report')
    
    def __init__(self, *args, **kwargs):
        super(OccupancyForm, self).__init__(*args, **kwargs)
        self.screen_id.choices = [(0, 'All Screens')] + [(s.id, s.name) for s in Screen.query.all()]
        self.movie_id.choices = [(0, 'All Movies')] + [(m.id, m.title) for m in Movie.query.filter_by(status='active').all()]

class CashierSummaryForm(FlaskForm):
    """Form for cashier summary report filters"""
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    cashier_id = SelectField('Cashier', coerce=int, validators=[Optional()])
    submit = SubmitField('Filter Report')
    
    def __init__(self, *args, **kwargs):
        super(CashierSummaryForm, self).__init__(*args, **kwargs)
        self.cashier_id.choices = [(0, 'All Cashiers')] + [(u.id, u.username) for u in User.query.filter(User.role.in_(['admin', 'cashier'])).all()]

class MoviePerformanceForm(FlaskForm):
    """Form for movie performance report filters"""
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    movie_id = SelectField('Movie', coerce=int, validators=[Optional()])
    submit = SubmitField('Filter Report')
    
    def __init__(self, *args, **kwargs):
        super(MoviePerformanceForm, self).__init__(*args, **kwargs)
        self.movie_id.choices = [(0, 'All Movies')] + [(m.id, m.title) for m in Movie.query.filter_by(status='active').all()]

class ScreenUtilizationForm(FlaskForm):
    """Form for screen utilization report filters"""
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    screen_id = SelectField('Screen', coerce=int, validators=[Optional()])
    submit = SubmitField('Filter Report')
    
    def __init__(self, *args, **kwargs):
        super(ScreenUtilizationForm, self).__init__(*args, **kwargs)
        self.screen_id.choices = [(0, 'All Screens')] + [(s.id, s.name) for s in Screen.query.all()]

class ExportForm(FlaskForm):
    """Form for export options"""
    export_format = RadioField('Export Format', 
                              choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')], 
                              default='pdf')
    submit = SubmitField('Export Report')

class ReportTypeForm(FlaskForm):
    """Form for report type selection"""
    report_type = SelectField('Report Type', 
                             choices=[
                                 ('sales', 'Sales Report'),
                                 ('occupancy', 'Occupancy Report'),
                                 ('cashier', 'Cashier Summary'),
                                 ('movies', 'Movie Performance'),
                                 ('screens', 'Screen Utilization')
                             ], 
                             validators=[DataRequired()])
    submit = SubmitField('Generate Report')