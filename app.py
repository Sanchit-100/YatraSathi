# File: app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = 'supersecretkey'
bcrypt = Bcrypt(app)


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user['password_hash'] == password:
            session['user'] = user['user_id']
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials.')

        cursor.close()
        conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        hashed_pw = password  # You can hash later

        conn = get_db_connection()
        
        check_cursor = conn.cursor(dictionary=True)
        check_cursor.execute("SELECT * FROM User WHERE email = %s OR phone_number = %s", (email, phone))
        results = check_cursor.fetchall()
        existing_user = results[0] if results else None
        check_cursor.close()

        if existing_user:
            conn.close()
            flash('ID already exists with same email or phone.')
            return redirect(url_for('register'))

        insert_cursor = conn.cursor(dictionary=True)
        insert_cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
        result = insert_cursor.fetchone()
        next_user_id = (result['max_id'] or 0) + 1

        insert_cursor.execute("""
            INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
            VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
        """, (next_user_id, name, email, hashed_pw, phone))

        conn.commit()
        insert_cursor.close()
        conn.close()

        flash('Registered successfully. Please login.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/user/dashboard')
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/booking/flight')
def flight_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: render actual flight booking page
    return render_template('flight_booking.html')

@app.route('/booking/train')
def train_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: render actual train booking page
    return render_template('train_booking.html')

@app.route('/booking/bus')
def bus_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: render actual bus booking page
    return render_template('bus_booking.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: fetch user details from DB and pass to template
    return render_template('profile.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
# File: app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = 'supersecretkey'
bcrypt = Bcrypt(app)


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user['password_hash'] == password:
            session['user'] = user['user_id']
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials.')

        cursor.close()
        conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        hashed_pw = password  # You can hash later

        conn = get_db_connection()
        
        check_cursor = conn.cursor(dictionary=True)
        check_cursor.execute("SELECT * FROM User WHERE email = %s OR phone_number = %s", (email, phone))
        results = check_cursor.fetchall()
        existing_user = results[0] if results else None
        check_cursor.close()

        if existing_user:
            conn.close()
            flash('ID already exists with same email or phone.')
            return redirect(url_for('register'))

        insert_cursor = conn.cursor(dictionary=True)
        insert_cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
        result = insert_cursor.fetchone()
        next_user_id = (result['max_id'] or 0) + 1

        insert_cursor.execute("""
            INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
            VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
        """, (next_user_id, name, email, hashed_pw, phone))

        conn.commit()
        insert_cursor.close()
        conn.close()

        flash('Registered successfully. Please login.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/user/dashboard')
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
