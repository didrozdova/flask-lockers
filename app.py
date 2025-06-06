from flask import Flask, render_template, redirect, url_for, request, flash
from forms import RegisterForm, LoginForm, BookingForm
from models import db, User, Locker, Booking
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///boxes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()
    if not Locker.query.first():
        for i in range(1, 6):
            db.session.add(Locker(number=f"L-{i}"))
        db.session.commit()


# 🔄 Обновление статуса ячеек по актуальным броням
def update_locker_statuses():
    now = datetime.now()

    # Освобождаем ячейки с завершёнными бронями
    expired = Booking.query.filter(Booking.end_time < now).all()
    for booking in expired:
        if not booking.locker.is_available:
            booking.locker.is_available = True

    # Занимаем ячейки с активными бронями
    active = Booking.query.filter(
        Booking.start_time <= now,
        Booking.end_time >= now
    ).all()
    for booking in active:
        if booking.locker.is_available:
            booking.locker.is_available = False

    db.session.commit()

@app.before_request
def cleanup_before_request():
    now = datetime.now()

    # Удаляем брони с ошибочным временем
    invalid_bookings = Booking.query.filter(Booking.start_time >= Booking.end_time).all()
    for booking in invalid_bookings:
        db.session.delete(booking)

    # Освобождаем ячейки, если бронирование уже завершилось
    expired_bookings = Booking.query.filter(Booking.end_time <= now).all()
    for booking in expired_bookings:
        if not booking.locker.is_available:
            booking.locker.is_available = True

    db.session.commit()

@app.route('/')
def home():
    if current_user.is_authenticated:
        return f'Вы вошли как: {current_user.email} <a href="/logout">[Выйти]</a>'
    return 'Привет! Пожалуйста, <a href="/login">войдите</a>.'


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта.', 'info')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Вы вошли в систему!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Неверный email или пароль.', 'danger')
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        new_user = User(email=form.email.data, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация прошла успешно!', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', form=form)

@app.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    form = BookingForm()
    now = datetime.now()

    busy_locker_ids = db.session.query(Booking.locker_id).filter(
        Booking.start_time <= now,
        Booking.end_time > now
    ).subquery()

    available_lockers = Locker.query.filter(~Locker.id.in_(busy_locker_ids)).all()
    form.locker.choices = [(l.id, l.number) for l in available_lockers]

    if form.validate_on_submit():
        start = form.start_time.data
        end = form.end_time.data

        if start >= end:
            flash('Ошибка: время окончания должно быть позже начала.', 'danger')
            return render_template('book.html', form=form)

        # Проверка на пересечение с другими бронированиями
        conflicting = Booking.query.filter(
            Booking.locker_id == form.locker.data,
            Booking.end_time > start,
            Booking.start_time < end
        ).first()

        if conflicting:
            flash('Ошибка: выбранная ячейка уже занята в указанный интервал.', 'danger')
            return render_template('book.html', form=form)

        new_booking = Booking(
            user_id=current_user.id,
            locker_id=form.locker.data,
            start_time=start,
            end_time=end
        )

        # Если бронь активна сейчас — занять ячейку
        if start <= now < end:
            locker = Locker.query.get(form.locker.data)
            locker.is_available = False

        db.session.add(new_booking)
        db.session.commit()

        flash('Бронирование успешно создано!', 'success')
        return redirect(url_for('home'))

    return render_template('book.html', form=form)

@app.route('/profile')
@login_required
def profile():
    now = datetime.now()

    current = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.start_time <= now,
        Booking.end_time > now  # строго больше!
    ).join(Locker).all()

    future = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.start_time > now
    ).join(Locker).all()

    past = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.end_time <= now
    ).join(Locker).all()

    return render_template('profile.html', current=current, future=future, past=past)

@app.route('/pay/<int:booking_id>', methods=['POST'])
@login_required
def pay_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash("Вы не можете оплатить это бронирование.", "danger")
        return redirect(url_for('profile'))

    if booking.is_paid:
        flash("Это бронирование уже оплачено.", "info")
    else:
        booking.is_paid = True
        db.session.commit()
        flash("Бронирование успешно оплачено.", "success")

    return redirect(url_for('profile'))

@app.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash("Вы не можете отменить это бронирование.", "danger")
        return redirect(url_for('profile'))

    booking.locker.is_available = True
    db.session.delete(booking)
    db.session.commit()

    flash("Бронирование отменено.", "info")
    return redirect(url_for('profile'))


@app.route('/lockers')
def show_lockers():
    now = datetime.now()
    lockers = Locker.query.all()

    output = []
    for locker in lockers:
        active_booking = Booking.query.filter(
            Booking.locker_id == locker.id,
            Booking.start_time <= now,
            Booking.end_time >= now
        ).first()

        status = "занята" if active_booking else "свободна"
        output.append(f"{locker.number} — {status}")

    return '<br>'.join(output)


if __name__ == '__main__':
    app.run(debug=True)
