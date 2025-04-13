# File: app.py
# ... (keep existing imports) ...
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, get_flashed_messages
from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG
import os
import datetime # Ensure datetime is imported
from functools import wraps
import logging
import random
import string


app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here' # CHANGE THIS
bcrypt = Bcrypt(app)

# --- Database Connection ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        app.logger.error(f"Database connection error: {err}")
        return None

# --- Decorators ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def landing():
    session.pop('is_admin', None)
    session.pop('admin_user_name', None)
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'] # Assuming plain text for now as per original code

        conn = get_db_connection()
        if not conn:
             flash("Database connection failed. Please try again later.", "error")
             return render_template('login.html')

        cursor = conn.cursor(dictionary=True)
        try:
            # Fetching plain text password stored in 'password_hash' column
            cursor.execute("SELECT user_id, name, password_hash FROM User WHERE email = %s", (email,))
            user = cursor.fetchone()

            # !!! INSECURE: Plain text password comparison !!!
            # Check if user exists and the plain text password matches
            if user and user['password_hash'] == password:
                session['user'] = user['user_id']
                session['user_name'] = user['name']
                session.pop('is_admin', None)
                session.pop('admin_user_name', None)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Invalid email or password.', 'error')

        except mysql.connector.Error as err:
            app.logger.error(f"Database error during login: {err}")
            flash(f"An error occurred during login. Please try again.", "error")
        finally:
            cursor.close()
            conn.close()

    if request.method == 'GET':
        session.pop('is_admin', None)
        session.pop('admin_user_name', None)

    success_messages = get_flashed_messages(category_filter=['success'])
    return render_template('login.html', success_messages=success_messages)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'] # Storing plain text password
        phone = request.form['phone']

        # !!! INSECURE: Storing plain text password directly !!!
        # The original code used bcrypt but stored plain text.
        # For consistency with the login logic provided, store plain text here.
        # If security is paramount, BOTH registration and login MUST use hashing (e.g., bcrypt).
        plain_password_to_store = password

        conn = get_db_connection()
        if not conn:
             flash("Database connection failed.", "error")
             return render_template('register.html')

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT email, phone_number FROM User WHERE email = %s OR phone_number = %s", (email, phone))
            existing_user = cursor.fetchone()
            if existing_user:
                flash('Email or Phone number already exists.', 'error')
                return redirect(url_for('register'))

            cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
            result = cursor.fetchone()
            next_user_id = (result['max_id'] or 0) + 1

            # Insert new user with PLAIN TEXT password in password_hash column
            cursor.execute("""
                INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
                VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
            """, (next_user_id, name, email, plain_password_to_store, phone)) # Storing plain password

            conn.commit()
            flash('Registered successfully. Please login.', 'success')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
             app.logger.error(f"Database error during registration: {err}")
             flash(f"An error occurred: {err}", "error")
             if conn.is_connected(): conn.rollback()
        finally:
            cursor.close()
            if conn.is_connected(): conn.close()

    return render_template('register.html')


@app.route('/user/dashboard')
@login_required
def user_dashboard():
    return render_template('user_dashboard.html', username=session.get('user_name'))


@app.route('/booking', methods=['GET'])
@login_required
def booking():
    conn = get_db_connection()
    if not conn:
        flash("Could not connect to the database.", "error")
        return redirect(url_for('user_dashboard'))

    cursor = conn.cursor(dictionary=True)
    stations = []
    transport_types = []
    available_transports = []
    source_station_name = request.args.get('source_station')
    destination_station_name = request.args.get('destination_station')
    travel_date_str = request.args.get('travel_date')
    transport_type = request.args.get('transport_type')

    try:
        cursor.execute("SELECT DISTINCT name FROM Station ORDER BY name")
        stations = cursor.fetchall()
        cursor.execute("SELECT DISTINCT type FROM Transport WHERE status = 'active' ORDER BY type")
        transport_types = cursor.fetchall()

        query = """
            SELECT
                t.transport_id, t.name AS transport_name, t.type AS transport_type, t.operator,
                s.schedule_id, s.departure_time, s.arrival_time, s.duration_hours,
                r.route_id, r.distance_km,
                st_source.name AS source_station_name,
                st_dest.name AS destination_station_name,
                (SELECT MIN(se.price) FROM Seat se WHERE se.transport_id = t.transport_id AND se.seat_id NOT IN (SELECT seat_id FROM Booking WHERE schedule_id = s.schedule_id AND status = 'confirmed')) AS min_price
            FROM Schedule s
            JOIN Transport t ON s.transport_id = t.transport_id
            JOIN Route r ON s.route_id = r.route_id
            JOIN Station st_source ON r.source_id = st_source.station_id
            JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE t.status = 'active'
        """
        params = []
        if source_station_name:
            query += " AND st_source.name = %s"; params.append(source_station_name)
        if destination_station_name:
            query += " AND st_dest.name = %s"; params.append(destination_station_name)
        if travel_date_str:
            try:
                travel_date = datetime.datetime.strptime(travel_date_str, '%Y-%m-%d').date()
                query += " AND DATE(s.departure_time) = %s"; params.append(travel_date)
            except ValueError: flash("Invalid date format.", "warning")
        if transport_type:
            query += " AND t.type = %s"; params.append(transport_type)
        query += " ORDER BY s.departure_time"
        cursor.execute(query, tuple(params))
        available_transports = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Database error fetching booking data: {err}")
        flash("An error occurred while fetching transport data.", "error")
    finally:
        cursor.close()
        conn.close()

    return render_template('booking.html',
                           stations=stations,
                           transport_types=transport_types,
                           transports=available_transports,
                           selected_source=source_station_name,
                           selected_destination=destination_station_name,
                           selected_date=travel_date_str,
                           selected_type=transport_type,
                           username=session.get('user_name'))

# --- Placeholder booking routes ---
@app.route('/booking/flight')
@login_required
def flight_booking():
    flash("Flight booking page is under construction.", "info")
    return render_template('flight_booking.html', username=session.get('user_name'))

@app.route('/booking/train')
@login_required
def train_booking():
    flash("Train booking page is under construction.", "info")
    return render_template('train_booking.html', username=session.get('user_name'))

@app.route('/booking/bus')
@login_required
def bus_booking():
    flash("Bus booking page is under construction.", "info")
    return render_template('bus_booking.html', username=session.get('user_name'))


# --- Profile Routes ---
@app.route('/profile')
@login_required
def profile():
    user_id = session['user']
    conn = get_db_connection()
    if not conn:
        flash("Could not connect to database.", "error")
        return redirect(url_for('user_dashboard'))

    cursor = conn.cursor(dictionary=True)
    user_data = None
    try:
        cursor.execute("SELECT user_id, name, email, phone_number, Refunds FROM User WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            flash("User profile not found.", "error"); session.clear(); return redirect(url_for('login'))
    except mysql.connector.Error as err:
        app.logger.error(f"Error loading profile: {err}")
        flash(f"Error loading profile.", "error")
        return redirect(url_for('user_dashboard'))
    finally:
        cursor.close()
        conn.close()
    return render_template('profile.html', user=user_data, username=session.get('user_name'))


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user']
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']

    conn = get_db_connection()
    if not conn:
        flash("Database connection error.", "error")
        return redirect(url_for('profile'))

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM User WHERE (email = %s OR phone_number = %s) AND user_id != %s", (email, phone, user_id))
        existing = cursor.fetchone()
        if existing:
             flash("Email or Phone number is already in use.", "error")
             return redirect(url_for('profile'))

        cursor.execute("UPDATE User SET name = %s, email = %s, phone_number = %s WHERE user_id = %s",
                       (name, email, phone, user_id))
        conn.commit()
        session['user_name'] = name
        flash("Profile updated successfully!", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error updating profile: {err}")
        flash(f"Error updating profile: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('profile'))


@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    user_id = session['user']
    current_password = request.form['current_password'] # Plain text
    new_password = request.form['new_password'] # Plain text
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for('profile'))
    if not new_password:
         flash("New password cannot be empty.", "error")
         return redirect(url_for('profile'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error.", "error")
        return redirect(url_for('profile'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch the stored PLAIN TEXT password
        cursor.execute("SELECT password_hash FROM User WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
             flash("User not found.", "error"); return redirect(url_for('login'))

        # !!! INSECURE: Plain text password comparison !!!
        if user['password_hash'] == current_password:
            # Update the database with the new PLAIN TEXT password
            update_cursor = conn.cursor()
            update_cursor.execute("UPDATE User SET password_hash = %s WHERE user_id = %s", (new_password, user_id))
            conn.commit()
            update_cursor.close()
            flash("Password updated successfully!", "success")
        else:
            flash("Incorrect current password.", "error")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error changing password: {err}")
        flash(f"Error changing password: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('profile'))

# --- NEW Cancellation Route (GET) ---
@app.route('/cancellation')
@login_required
def cancellation():
    user_id = session['user']
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('user_dashboard'))

    cursor = conn.cursor(dictionary=True)
    current_bookings = []
    cancellations = []

    try:
        # Fetch current (confirmed) bookings with details
        # Added Payment amount for context
        cursor.execute("""
            SELECT
                b.booking_id, b.pnr_number, b.booking_date,
                sch.departure_time, sch.arrival_time,
                t.name AS transport_name, t.type AS transport_type,
                st_source.name AS source_station_name,
                st_dest.name AS destination_station_name,
                se.seat_number, se.seat_class,
                p.amount
            FROM Booking b
            JOIN Schedule sch ON b.schedule_id = sch.schedule_id
            JOIN Transport t ON sch.transport_id = t.transport_id
            JOIN Route r ON sch.route_id = r.route_id
            JOIN Station st_source ON r.source_id = st_source.station_id
            JOIN Station st_dest ON r.destination_id = st_dest.station_id
            JOIN Seat se ON b.seat_id = se.seat_id
            LEFT JOIN Payment p ON b.booking_id = p.booking_id AND p.payment_status = 'completed'
            WHERE b.user_id = %s AND b.status = 'confirmed'
            ORDER BY sch.departure_time ASC
        """, (user_id,))
        current_bookings = cursor.fetchall()

        # Fetch past cancellations with details
        cursor.execute("""
            SELECT
                c.cancellation_id, c.booking_id, c.cancellation_date, c.refund_amount, c.refund_status,
                b.pnr_number,
                sch.departure_time,
                t.name AS transport_name, t.type AS transport_type
            FROM Cancellation c
            JOIN Booking b ON c.booking_id = b.booking_id
            JOIN Schedule sch ON b.schedule_id = sch.schedule_id
            JOIN Transport t ON sch.transport_id = t.transport_id
            WHERE b.user_id = %s
            ORDER BY c.cancellation_date DESC
        """, (user_id,))
        cancellations = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Database error fetching cancellation data for user {user_id}: {err}")
        flash("An error occurred while fetching your booking/cancellation history.", "error")
    finally:
        cursor.close()
        conn.close()

    return render_template('cancellation.html',
                           current_bookings=current_bookings,
                           cancellations=cancellations,
                           username=session.get('user_name'))


# --- NEW User Cancellation Route (POST) ---
@app.route('/booking/<int:booking_id>/user_cancel', methods=['POST'])
@login_required
def user_cancel_booking(booking_id):
    user_id = session['user']
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Could not process cancellation.", "error")
        return redirect(url_for('cancellation'))

    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Verify Booking belongs to user and is 'confirmed'
        cursor.execute("""
            SELECT b.schedule_id, sch.departure_time, se.price
            FROM Booking b
            JOIN Schedule sch ON b.schedule_id = sch.schedule_id
            JOIN Seat se ON b.seat_id = se.seat_id
            WHERE b.booking_id = %s AND b.user_id = %s AND b.status = 'confirmed'
        """, (booking_id, user_id))
        booking_info = cursor.fetchone()

        if not booking_info:
            flash("Booking not found, already cancelled, or does not belong to you.", "error")
            return redirect(url_for('cancellation'))

        # 2. Calculate Refund Amount (Based on Project_Overview.pdf rules)
        # NOTE: The request asked for status "not-confirmed", not immediate refund processing.
        # We calculate the potential refund amount to store it.
        departure_time = booking_info['departure_time']
        now = datetime.datetime.now()
        time_diff = departure_time - now
        hours_diff = time_diff.total_seconds() / 3600
        original_price = booking_info['price'] or 0.00 # Get original seat price

        refund_percentage = 0.0
        if hours_diff >= 24: # 1 day or more
             refund_percentage = 0.75 # 75% refund
        elif 6 <= hours_diff < 24: # Between 6 and 24 hours
             refund_percentage = 0.25 # 25% refund
        # Less than 6 hours (including <1 hour) gets 0% refund according to the rules.
        # The rules '<1 day: 75%', '<6 hr: 25%', '<1 hr: Non refundable' imply >=1hr to <6hr is also 25%.

        calculated_refund = original_price * refund_percentage

        # 3. Start Transaction
        conn.start_transaction()

        # 4. Update Booking Status
        cursor.execute("UPDATE Booking SET status = 'cancelled' WHERE booking_id = %s", (booking_id,))

        # 5. Insert into Cancellation Table
        cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
        max_c_id = cursor.fetchone()['max_id']
        next_c_id = (max_c_id or 0) + 1

        cursor.execute("""
            INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (next_c_id, booking_id, calculated_refund, 'not-confirmed')) # Status as requested

        # --- Removed: Do NOT update User.Refunds here as per request ---
        # cursor.execute("UPDATE User SET Refunds = Refunds + %s WHERE user_id = %s", (calculated_refund, user_id))
        # --- End Removed ---

        # 6. Commit
        conn.commit()
        flash(f"Booking ID {booking_id} cancelled successfully. Refund status is 'Not Confirmed'.", "success")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Database error cancelling booking {booking_id} for user {user_id}: {err}")
        flash(f"Failed to cancel booking due to a database error: {err}", "error")
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Unexpected error cancelling booking {booking_id} for user {user_id}: {e}")
        flash("An unexpected error occurred during cancellation.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('cancellation'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---
# ... (keep existing admin routes: admin_login, admin_authenticate, admin_dashboard, etc.) ...
# ... Make sure all other admin routes like admin_view_schedule_bookings, admin_cancel_specific_booking, etc. are still present ...

@app.route('/admin_login', methods=['GET'])
def admin_login():
    if session.get('is_admin'): return redirect(url_for('admin_dashboard'))
    session.pop('user', None)
    session.pop('user_name', None)
    return render_template('admin_login.html')

@app.route('/admin_authenticate', methods=['POST'])
def admin_authenticate():
    email = request.form.get('email')
    password = request.form.get('password') # Plain text password from form

    conn = get_db_connection()
    if not conn:
        flash("Database connection error.", "error")
        return redirect(url_for('admin_login'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, name, password_hash FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            flash("Invalid credentials or not an admin.", "error")
            return redirect(url_for('admin_login'))

        # !!! INSECURE: Plain text password comparison !!!
        if user['password_hash'] == password:
            cursor.execute("SELECT admin_id FROM Admin WHERE user_id = %s", (user['user_id'],))
            admin_record = cursor.fetchone()
            if admin_record:
                session.clear()
                session['is_admin'] = True
                session['admin_user_id'] = user['user_id']
                session['admin_user_name'] = user['name']
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Access denied. Not an authorized admin.", "error")
                return redirect(url_for('admin_login'))
        else:
            flash("Invalid credentials or not an admin.", "error")
            return redirect(url_for('admin_login'))

    except mysql.connector.Error as err:
        app.logger.error(f"Database error during admin auth: {err}")
        flash("An error occurred during admin login.", "error")
        return redirect(url_for('admin_login'))
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return render_template('admin_dashboard.html', transports_with_schedules={}, search_term='', filter_type='', filter_status='')

    cursor = conn.cursor(dictionary=True)
    transports_with_schedules = {}
    search_term = request.args.get('search_term', '')
    filter_type = request.args.get('filter_type', '')
    filter_status = request.args.get('filter_status', '')

    try:
        transport_query = "SELECT transport_id, type, name, operator, total_seats, status FROM Transport"
        transport_params = []
        transport_conditions = []
        if search_term:
            search_like = f"%{search_term}%"
            transport_conditions.append("(name LIKE %s OR operator LIKE %s)")
            transport_params.extend([search_like, search_like])
        if filter_type:
            transport_conditions.append("type = %s")
            transport_params.append(filter_type)
        if filter_status:
            transport_conditions.append("status = %s")
            transport_params.append(filter_status)
        if transport_conditions:
            transport_query += " WHERE " + " AND ".join(transport_conditions)
        transport_query += " ORDER BY transport_id"

        cursor.execute(transport_query, tuple(transport_params))
        transports = cursor.fetchall()

        for transport in transports:
            transport_id = transport['transport_id']
            transports_with_schedules[transport_id] = {'details': transport, 'schedules': []}
            schedule_query = """
                SELECT s.schedule_id, s.departure_time, s.arrival_time, s.duration_hours, r.route_id, r.distance_km, st_source.name AS source_station_name, st_dest.name AS destination_station_name
                FROM Schedule s JOIN Route r ON s.route_id = r.route_id JOIN Station st_source ON r.source_id = st_source.station_id JOIN Station st_dest ON r.destination_id = st_dest.station_id
                WHERE s.transport_id = %s ORDER BY s.departure_time
            """
            cursor.execute(schedule_query, (transport_id,))
            schedules = cursor.fetchall()
            transports_with_schedules[transport_id]['schedules'] = schedules

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching data for admin dashboard: {err}")
        flash("Failed to load dashboard data.", "error")
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_dashboard.html',
                           transports_with_schedules=transports_with_schedules,
                           search_term=search_term, filter_type=filter_type, filter_status=filter_status,
                           username=session.get('admin_user_name'))


@app.route('/admin/schedule/<int:schedule_id>/bookings')
@admin_required
def admin_view_schedule_bookings(schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    bookings = []
    schedule_info = None
    try:
        cursor.execute("""
            SELECT s.schedule_id, t.name as transport_name, st_source.name AS source_station_name, st_dest.name AS destination_station_name, s.departure_time
            FROM Schedule s JOIN Transport t ON s.transport_id = t.transport_id JOIN Route r ON s.route_id = r.route_id JOIN Station st_source ON r.source_id = st_source.station_id JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE s.schedule_id = %s
        """, (schedule_id,))
        schedule_info = cursor.fetchone()
        if not schedule_info:
             flash(f"Schedule ID {schedule_id} not found.", "error")
             return redirect(url_for('admin_dashboard'))

        cursor.execute("""
            SELECT b.booking_id, b.booking_date, b.status, b.pnr_number, u.user_id, u.name AS user_name, u.email AS user_email, se.seat_id, se.seat_number, se.seat_class, se.price AS seat_price
            FROM Booking b JOIN User u ON b.user_id = u.user_id JOIN Seat se ON b.seat_id = se.seat_id
            WHERE b.schedule_id = %s ORDER BY b.booking_date DESC
        """, (schedule_id,))
        bookings = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching bookings for schedule {schedule_id}: {err}")
        flash("Failed to load booking data.", "error")
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_schedule_bookings.html', bookings=bookings, schedule_info=schedule_info, schedule_id=schedule_id, username=session.get('admin_user_name'))


@app.route('/admin/booking/<int:booking_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_specific_booking(booking_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(request.referrer or url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    schedule_id = None
    try:
        conn.start_transaction()
        cursor.execute("""
            SELECT b.user_id, b.seat_id, b.status, b.schedule_id, s.price
            FROM Booking b JOIN Seat s ON b.seat_id = s.seat_id
            WHERE b.booking_id = %s
        """, (booking_id,))
        booking = cursor.fetchone()
        if not booking:
            flash(f"Booking ID {booking_id} not found.", "error")
            conn.rollback(); cursor.close(); conn.close()
            return redirect(request.referrer or url_for('admin_dashboard'))

        schedule_id = booking['schedule_id']
        if booking['status'] != 'confirmed':
            flash(f"Booking {booking_id} not 'confirmed'. Cannot cancel.", "warning")
            conn.rollback(); cursor.close(); conn.close()
            return redirect(url_for('admin_view_schedule_bookings', schedule_id=schedule_id))

        user_id = booking['user_id']
        refund_amount = booking['price'] or 0.0
        cursor.execute("UPDATE Booking SET status = 'cancelled_by_admin' WHERE booking_id = %s", (booking_id,))
        cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
        next_c_id = (cursor.fetchone()['max_id'] or 0) + 1
        cursor.execute("""
            INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
            VALUES (%s, %s, NOW(), %s, 'completed')
        """, (next_c_id, booking_id, refund_amount))
        cursor.execute("UPDATE User SET Refunds = Refunds + %s WHERE user_id = %s", (refund_amount, user_id))
        conn.commit()
        flash(f"Booking ID {booking_id} cancelled, ₹{refund_amount:.2f} refunded.", "success")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error cancelling booking {booking_id}: {err}")
        flash(f"Failed to cancel booking: {err}", "error")
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Unexpected error cancelling booking {booking_id}: {e}")
        flash("An unexpected error occurred.", "error")
    finally:
        cursor.close()
        conn.close()

    if schedule_id:
        return redirect(url_for('admin_view_schedule_bookings', schedule_id=schedule_id))
    else:
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/edit_schedule/<int:schedule_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_schedule(schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    schedule = None # Define schedule here

    # Fetch schedule details first for both GET and POST (if POST fails validation)
    try:
        query = """
            SELECT s.*, t.name as transport_name, t.type as transport_type, st_source.name AS source_station_name, st_dest.name AS destination_station_name
            FROM Schedule s JOIN Transport t ON s.transport_id = t.transport_id JOIN Route r ON s.route_id = r.route_id JOIN Station st_source ON r.source_id = st_source.station_id JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE s.schedule_id = %s
        """
        cursor.execute(query, (schedule_id,))
        schedule = cursor.fetchone()
        if not schedule:
            flash(f"Schedule ID {schedule_id} not found.", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))
        # Format times for the datetime-local input type value attribute
        schedule['departure_time_str'] = schedule['departure_time'].strftime('%Y-%m-%dT%H:%M') if schedule.get('departure_time') else ''
        schedule['arrival_time_str'] = schedule['arrival_time'].strftime('%Y-%m-%dT%H:%M') if schedule.get('arrival_time') else ''

    except mysql.connector.Error as err:
         app.logger.error(f"Error fetching schedule {schedule_id} for edit: {err}")
         flash("Failed to load schedule data.", "error")
         if cursor and conn.is_connected(): cursor.close(); conn.close()
         return redirect(url_for('admin_dashboard'))


    if request.method == 'POST':
        new_departure_str = request.form.get('departure_time')
        new_arrival_str = request.form.get('arrival_time')
        try:
            new_departure = datetime.datetime.strptime(new_departure_str, '%Y-%m-%dT%H:%M')
            new_arrival = datetime.datetime.strptime(new_arrival_str, '%Y-%m-%dT%H:%M')
            if new_arrival <= new_departure:
                flash("Arrival time must be after departure time.", "error")
                # No need to fetch again, schedule is already fetched above
                cursor.close(); conn.close()
                return render_template('edit_schedule.html', schedule=schedule, username=session.get('admin_user_name'))

            duration = new_arrival - new_departure
            duration_hours = duration.total_seconds() / 3600
            cursor.execute("""
                UPDATE Schedule SET departure_time = %s, arrival_time = %s, duration_hours = %s
                WHERE schedule_id = %s
            """, (new_departure, new_arrival, duration_hours, schedule_id))
            conn.commit()
            flash(f"Schedule ID {schedule_id} updated.", "success")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

        except ValueError:
            flash("Invalid date/time format.", "error")
            cursor.close(); conn.close()
            return render_template('edit_schedule.html', schedule=schedule, username=session.get('admin_user_name'))
        except mysql.connector.Error as err:
            conn.rollback()
            app.logger.error(f"Error updating schedule {schedule_id}: {err}")
            flash(f"Failed to update schedule: {err}", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

    # --- GET Request ---
    # Schedule is already fetched above
    cursor.close(); conn.close()
    return render_template('edit_schedule.html', schedule=schedule, username=session.get('admin_user_name'))


@app.route('/admin/cancel_schedule/<int:schedule_id>', methods=['POST'])
@admin_required
def admin_cancel_schedule(schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error"); return redirect(url_for('admin_dashboard'))
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        cursor.execute("""
            SELECT b.booking_id, b.user_id, b.seat_id, s.price
            FROM Booking b JOIN Seat s ON b.seat_id = s.seat_id
            WHERE b.schedule_id = %s AND b.status = 'confirmed'
        """, (schedule_id,))
        bookings_to_cancel = cursor.fetchall()

        cancelled_booking_count = 0; total_refund_processed = 0.0
        for booking in bookings_to_cancel:
            booking_id = booking['booking_id']; user_id = booking['user_id']
            refund_amount = booking['price'] or 0.0
            cursor.execute("UPDATE Booking SET status = 'cancelled_by_admin' WHERE booking_id = %s", (booking_id,))
            cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
            next_c_id = (cursor.fetchone()['max_id'] or 0) + 1
            cursor.execute("""
                INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
                VALUES (%s, %s, NOW(), %s, %s)
            """, (next_c_id, booking_id, refund_amount, 'completed'))
            cursor.execute("UPDATE User SET Refunds = Refunds + %s WHERE user_id = %s", (refund_amount, user_id))
            cancelled_booking_count += 1; total_refund_processed += float(refund_amount)

        conn.commit()
        if cancelled_booking_count > 0:
             flash(f"{cancelled_booking_count} bookings cancelled for Sch. {schedule_id}, ₹{total_refund_processed:.2f} refunded.", "success")
        else:
             flash(f"No active bookings for Sch. {schedule_id}.", "info")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error cancelling schedule {schedule_id}: {err}")
        flash(f"Failed to cancel schedule bookings: {err}", "error")
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Unexpected error cancelling schedule {schedule_id}: {e}")
        flash("An unexpected error occurred.", "error")
    finally:
        cursor.close(); conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/prices/<int:transport_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_prices(transport_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    transport = None # Define transport

    # Fetch transport and seats first for GET and POST error cases
    try:
        cursor.execute("SELECT name, type FROM Transport WHERE transport_id = %s", (transport_id,))
        transport = cursor.fetchone()
        if not transport:
            flash(f"Transport ID {transport_id} not found.", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

        cursor.execute("SELECT seat_id, seat_number, seat_class, price FROM Seat WHERE transport_id = %s ORDER BY seat_class, seat_number", (transport_id,))
        seats = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching data for transport {transport_id} prices: {err}")
        flash("Failed to load data for editing prices.", "error")
        if cursor and conn.is_connected(): cursor.close(); conn.close()
        return redirect(url_for('admin_dashboard'))


    if request.method == 'POST':
        try:
            updated_count = 0; error_count = 0
            conn.start_transaction() # Use transaction
            for key, value in request.form.items():
                if key.startswith('price_'):
                    try:
                        seat_id = int(key.split('_')[1])
                        new_price = float(value)
                        if new_price < 0:
                             flash(f"Price for Seat ID {seat_id} cannot be negative.", "error")
                             error_count += 1; continue
                        cursor.execute("UPDATE Seat SET price = %s WHERE seat_id = %s AND transport_id = %s",
                                       (new_price, seat_id, transport_id))
                        if cursor.rowcount > 0: updated_count += 1
                    except (ValueError, IndexError):
                        app.logger.warning(f"Invalid price form data: key={key}, value={value}")
                        error_count += 1
                    except mysql.connector.Error as err:
                         app.logger.error(f"Error updating price for seat derived from {key}: {err}")
                         flash(f"DB error updating price for Seat ID {key.split('_')[1]}.", "error")
                         error_count += 1; break # Stop on first DB error

            if error_count == 0:
                 conn.commit(); flash(f"{updated_count} prices updated for Transport {transport_id}.", "success")
            else:
                conn.rollback(); flash(f"Errors occurred. No prices updated.", "error")

        except Exception as e:
             if conn.is_connected(): conn.rollback() # Rollback on general error too
             app.logger.error(f"General error processing price updates for {transport_id}: {e}")
             flash("An unexpected error occurred.", "error")
        finally:
             cursor.close(); conn.close()
        # Redirect back to dashboard after POST
        return redirect(url_for('admin_dashboard'))

    # --- GET Request ---
    # Transport and seats already fetched
    cursor.close(); conn.close()
    return render_template('edit_prices.html', transport=transport, seats=seats, transport_id=transport_id, username=session.get('admin_user_name'))


@app.route('/admin/add_transport', methods=['POST'])
@admin_required
def admin_add_transport():
    conn = get_db_connection()
    if not conn:
        flash("DB connection failed.", "error"); return redirect(url_for('admin_dashboard'))
    cursor = conn.cursor()
    try:
        type = request.form.get('type')
        name = request.form.get('name')
        operator = request.form.get('operator')
        total_seats = request.form.get('total_seats', type=int)
        status = request.form.get('status')
        if not all([type, name, operator, total_seats is not None, status]):
             flash("All fields required.", "error"); return redirect(url_for('admin_dashboard'))
        if total_seats <= 0:
            flash("Seats must be positive.", "error"); return redirect(url_for('admin_dashboard'))
        cursor.execute("SELECT MAX(transport_id) AS max_id FROM Transport")
        next_id = (cursor.fetchone()[0] or 0) + 1
        cursor.execute("INSERT INTO Transport VALUES (%s, %s, %s, %s, %s, %s)",
                       (next_id, type, name, operator, total_seats, status))
        conn.commit()
        flash(f"Transport '{name}' added.", "success")
    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error adding transport: {err}")
        flash(f"Failed to add transport: {err}", "error")
    except ValueError: flash("Invalid seats number.", "error")
    finally: cursor.close(); conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_transport/<int:transport_id>', methods=['POST'])
@admin_required
def admin_delete_transport(transport_id):
    conn = get_db_connection()
    if not conn:
        flash("DB connection failed.", "error"); return redirect(url_for('admin_dashboard'))
    cursor = conn.cursor()
    try:
        # WARNING: Add checks for related schedules/bookings before deleting in production
        cursor.execute("DELETE FROM Transport WHERE transport_id = %s", (transport_id,))
        conn.commit()
        if cursor.rowcount > 0: flash(f"Transport ID {transport_id} deleted.", "success")
        else: flash(f"Transport ID {transport_id} not found.", "warning")
    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error deleting transport {transport_id}: {err}")
        if 'foreign key constraint' in str(err).lower(): # Basic check
             flash(f"Cannot delete Transport {transport_id}: It is referenced elsewhere.", "error")
        else: flash(f"Failed to delete transport {transport_id}: {err}", "error")
    finally: cursor.close(); conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_user_id', None)
    session.pop('admin_user_name', None)
    flash('Admin logged out.', 'success')
    return redirect(url_for('admin_login'))


@app.route('/booking/<transport_type>/<int:schedule_id>', methods=['GET'])
@login_required
def select_seats(transport_type, schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('booking'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Get transport and schedule details
        cursor.execute("""
            SELECT t.transport_id, t.name AS transport_name, t.type AS transport_type, t.operator,
                   s.schedule_id, s.departure_time, s.arrival_time,
                   st_source.name AS source_station_name,
                   st_dest.name AS destination_station_name
            FROM Transport t
            JOIN Schedule s ON t.transport_id = s.transport_id
            JOIN Route r ON s.route_id = r.route_id
            JOIN Station st_source ON r.source_id = st_source.station_id
            JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE s.schedule_id = %s AND t.type = %s
        """, (schedule_id, transport_type))
        transport = cursor.fetchone()
        if not transport:
            flash("Transport schedule not found.", "error")
            return redirect(url_for('booking'))

        # Get all seats with their booking status
        cursor.execute("""
            SELECT s.seat_id, s.seat_number, s.seat_class, s.price,
                   CASE WHEN b.booking_id IS NOT NULL AND b.status = 'confirmed' THEN 'booked'
                        ELSE 'available' END AS status
            FROM Seat s
            LEFT JOIN Booking b ON s.seat_id = b.seat_id AND b.schedule_id = %s
            WHERE s.transport_id = %s
            ORDER BY s.seat_number
        """, (schedule_id, transport['transport_id']))
        seats = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Database error fetching seat data: {err}")
        flash("An error occurred while fetching seat data.", "error")
        return redirect(url_for('booking'))
    finally:
        cursor.close()
        conn.close()

    return render_template('seat_selection.html', transport=transport, seats=seats)

@app.route('/booking/<transport_type>/<int:schedule_id>/confirm', methods=['POST'])
@login_required
def confirm_booking(transport_type, schedule_id):
    user_id = session['user']
    selected_seats = request.form.get('selected_seats', '').split(',')
    
    if not selected_seats or selected_seats[0] == '':
        flash("Please select at least one seat.", "error")
        return redirect(url_for('select_seats', transport_type=transport_type, schedule_id=schedule_id))

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('booking'))

    cursor = conn.cursor(dictionary=True)
    
    # Generate PNR
    pnr = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    try:
        # Check if seats are available (simpler query)
        total_amount = 0
        booking_ids = []
        
        # Process each seat individually
        for seat_id in selected_seats:
            if not seat_id:
                continue
                
            # Get seat price and check availability
            cursor.execute("""
                SELECT seat_id, price 
                FROM Seat 
                WHERE seat_id = %s
            """, (seat_id,))
            seat = cursor.fetchone()
            
            if not seat:
                flash(f"Seat {seat_id} not found.", "error")
                continue
                
            # Check if seat is already booked
            cursor.execute("""
                SELECT booking_id FROM Booking 
                WHERE seat_id = %s AND schedule_id = %s AND status = 'confirmed'
            """, (seat_id, schedule_id))
            
            if cursor.fetchone():
                flash(f"Seat {seat_id} is already booked.", "error")
                continue
                
            # Generate new booking ID
            cursor.execute("SELECT MAX(booking_id) as max_id FROM Booking")
            result = cursor.fetchone()
            next_booking_id = (result['max_id'] or 0) + 1
            
            # Create booking record
            cursor.execute("""
                INSERT INTO Booking (booking_id, user_id, schedule_id, seat_id, booking_date, status, pnr_number)
                VALUES (%s, %s, %s, %s, NOW(), 'confirmed', %s)
            """, (next_booking_id, user_id, schedule_id, seat_id, pnr))
            
            booking_ids.append(next_booking_id)
            total_amount += seat['price']
            
        # If no seats were successfully booked
        if not booking_ids:
            flash("No seats were available to book.", "error")
            return redirect(url_for('select_seats', transport_type=transport_type, schedule_id=schedule_id))
            
        # Create payment record using first booking ID
        cursor.execute("SELECT MAX(payment_id) as max_id FROM Payment")
        result = cursor.fetchone()
        next_payment_id = (result['max_id'] or 0) + 1
        
        # Insert payment with required fields based on the schema
        cursor.execute("""
            INSERT INTO Payment (payment_id, booking_id, amount, payment_method, transaction_id, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (next_payment_id, booking_ids[0], total_amount, 'credit_card', f'TXN-{pnr}', 'completed'))
        
        conn.commit()
        # Instead of redirecting immediately, render the success page
        cursor.close()
        conn.close()
        return render_template('booking_success.html', pnr=pnr)
        
    except mysql.connector.Error as err:
        app.logger.error(f"Database error during booking: {err}")
        flash(f"An error occurred: {err}", "error")
        return redirect(url_for('select_seats', transport_type=transport_type, schedule_id=schedule_id))
    finally:
        cursor.close()
        conn.close()

# --- Main Execution ---
if __name__ == '__main__':
    # Configure basic logging
    logging.basicConfig(level=logging.INFO)
    app.logger.info("Starting YatraSathi application...")
    app.run(debug=True)