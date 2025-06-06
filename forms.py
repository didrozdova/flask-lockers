from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateTimeLocalField, BooleanField
from wtforms.validators import DataRequired, Email, Length

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class BookingForm(FlaskForm):
    locker = SelectField('Выберите ячейку', coerce=int)
    start_time = DateTimeLocalField('Начало', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_time = DateTimeLocalField('Окончание', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    submit = SubmitField('Забронировать')
