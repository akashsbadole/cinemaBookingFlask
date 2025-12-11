"""
Screens Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, DecimalField, HiddenField, BooleanField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional

class ScreenForm(FlaskForm):
    """Screen form for adding and editing screens"""
    name = StringField('Screen Name', validators=[DataRequired()])
    total_rows = IntegerField('Total Rows', validators=[
        DataRequired(),
        NumberRange(min=1, max=20, message='Rows must be between 1 and 20')
    ])
    total_columns = IntegerField('Total Columns', validators=[
        DataRequired(),
        NumberRange(min=1, max=20, message='Columns must be between 1 and 20')
    ])
    submit = SubmitField('Save Screen')

class SeatForm(FlaskForm):
    """Seat form for creating and editing individual seats"""
    screen_id = HiddenField('Screen ID', validators=[DataRequired()])
    row = SelectField('Row', validators=[DataRequired()], coerce=str)
    column = SelectField('Column', validators=[DataRequired()], coerce=int)
    type = SelectField('Seat Type', choices=[
        ('normal', 'Normal'),
        ('premium', 'Premium'),
        ('vip', 'VIP')
    ], validators=[DataRequired()])
    price = DecimalField('Price', places=2, validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be a positive number')
    ])
    submit = SubmitField('Save Seat')

class BulkSeatForm(FlaskForm):
    """Form for bulk seat operations"""
    screen_id = HiddenField('Screen ID', validators=[DataRequired()])
    pattern = SelectField('Seat Pattern', choices=[
        ('regular', 'Regular Layout'),
        ('stadium', 'Stadium Layout'),
        ('mixed', 'Mixed Types')
    ], validators=[DataRequired()])
    normal_price = DecimalField('Normal Price', places=2, validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be a positive number')
    ])
    premium_price = DecimalField('Premium Price', places=2, validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be a positive number')
    ])
    vip_price = DecimalField('VIP Price', places=2, validators=[
        DataRequired(),
        NumberRange(min=0, message='Price must be a positive number')
    ])
    clear_existing = BooleanField('Clear existing seats before generating new ones', default=False)
    submit = SubmitField('Generate Seats')

class SeatLayoutForm(FlaskForm):
    """Form for defining custom seat layouts"""
    screen_id = HiddenField('Screen ID', validators=[DataRequired()])
    layout_definition = TextAreaField('Layout Definition', validators=[DataRequired()],
                                     description='Define seat types per row. Format: ROW:TYPE_PATTERN (e.g., A:NNNPPV for Normal, Premium, Premium, VIP)')
    submit = SubmitField('Apply Layout')