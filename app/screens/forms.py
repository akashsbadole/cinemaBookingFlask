"""
Screens Forms
"""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange

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