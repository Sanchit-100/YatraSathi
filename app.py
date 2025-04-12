# File: app.py
# Corrected import line below
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, get_flashed_messages
from flask_bcrypt import Bcrypt # Import Bcrypt
import mysql.connector
from config import DB_CONFIG
import os
import datetime
from functools import wraps # For decorators
import logging

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here' # CHANGE THIS in production! Use a strong, random key.
bcrypt = Bcrypt(app) # Initialize Bcrypt

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
    # Clear admin session if visiting landing page
    session.pop('is_admin', None)
    session.pop('admin_user_name', None)
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
             flash("Database connection failed. Please try again later.", "error")
             return render_template('login.html')

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT user_id, name, password_hash FROM User WHERE email = %s", (email,))
            user = cursor.fetchone()

            # Verify password using bcrypt
            if user and user['password_hash'] == password:
                session['user'] = user['user_id']
                session['user_name'] = user['name']
                # Clear any potential stale admin flag from previous sessions
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

    # Clear any admin session if reaching user login page via GET
    if request.method == 'GET':
        session.pop('is_admin', None)
        session.pop('admin_user_name', None)

    # Pass success messages if redirected from registration
    # Use the now-imported get_flashed_messages
    success_messages = get_flashed_messages(category_filter=['success'])
    return render_template('login.html', success_messages=success_messages)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        # Hash the password securely
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        if not conn:
             flash("Database connection failed. Please try again later.", "error")
             return render_template('register.html')

        cursor = conn.cursor(dictionary=True)
        try:
            # Check for existing email or phone
            cursor.execute("SELECT email, phone_number FROM User WHERE email = %s OR phone_number = %s", (email, phone))
            existing_user = cursor.fetchone()

            if existing_user:
                if existing_user['email'] == email:
                    flash('Email already exists.', 'error')
                else: # Must be the phone number
                    flash('Phone number already exists.', 'error')
                return redirect(url_for('register'))

            # Get next user ID (Consider using AUTO_INCREMENT in your DB schema)
            cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
            result = cursor.fetchone()
            next_user_id = (result['max_id'] or 0) + 1

            # Insert new user with hashed password
            cursor.execute("""
                INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
                VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
            """, (next_user_id, name, email, hashed_pw, phone)) # Use hashed_pw

            conn.commit()
            flash('Registered successfully. Please login.', 'success')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
             app.logger.error(f"Database error during registration: {err}")
             flash(f"An error occurred during registration: {err}", "error")
             if conn.is_connected():
                 conn.rollback()
        finally:
            cursor.close()
            if conn.is_connected():
                 conn.close()

    return render_template('register.html')


@app.route('/user/dashboard')
@login_required # Use decorator
def user_dashboard():
    return render_template('user_dashboard.html', username=session.get('user_name'))


@app.route('/booking', methods=['GET'])
@login_required # Use decorator
def booking():
    conn = get_db_connection()
    if not conn:
        flash("Could not connect to the database. Please try again later.", "error")
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
        # Fetch stations and types (no changes needed here)
        cursor.execute("SELECT DISTINCT name FROM Station ORDER BY name")
        stations = cursor.fetchall()
        cursor.execute("SELECT DISTINCT type FROM Transport WHERE status = 'active' ORDER BY type")
        transport_types = cursor.fetchall()

        # Filtering Logic (no changes needed here)
        query = """
            SELECT
                t.transport_id, t.name AS transport_name, t.type AS transport_type, t.operator,
                s.schedule_id, s.departure_time, s.arrival_time, s.duration_hours,
                r.route_id, r.distance_km,
                st_source.name AS source_station_name,
                st_dest.name AS destination_station_name,
                (SELECT MIN(se.price) FROM Seat se WHERE se.transport_id = t.transport_id) AS min_price
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
            except ValueError: flash("Invalid date format. Please use YYYY-MM-DD.", "warning")
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
        flash("Could not connect to the database to load profile.", "error")
        return redirect(url_for('user_dashboard'))

    cursor = conn.cursor(dictionary=True)
    user_data = None
    try:
        cursor.execute("SELECT user_id, name, email, phone_number, Refunds FROM User WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data: # Should not happen if session is valid, but good check
            flash("User profile not found.", "error"); session.clear(); return redirect(url_for('login'))
    except mysql.connector.Error as err:
        app.logger.error(f"Error loading profile: {err}")
        flash(f"Error loading profile.", "error")
        return redirect(url_for('user_dashboard'))
    finally:
        cursor.close()
        conn.close()
    return render_template('profile.html', user=user_data)


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user']
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']

    conn = get_db_connection()
    if not conn:
        flash("Database connection error. Could not update profile.", "error")
        return redirect(url_for('profile'))

    cursor = conn.cursor()
    try:
        # Check if email or phone is already taken by *another* user
        cursor.execute("SELECT user_id FROM User WHERE (email = %s OR phone_number = %s) AND user_id != %s", (email, phone, user_id))
        existing = cursor.fetchone()
        if existing:
             flash("Email or Phone number is already in use by another account.", "error")
             return redirect(url_for('profile'))

        # Update user details
        cursor.execute("UPDATE User SET name = %s, email = %s, phone_number = %s WHERE user_id = %s",
                       (name, email, phone, user_id))
        conn.commit()
        session['user_name'] = name # Update session name if changed
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
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for('profile'))

    if not new_password: # Basic validation
         flash("New password cannot be empty.", "error")
         return redirect(url_for('profile'))

    conn = get_db_connection()
    if not conn:
        flash("Database connection error. Could not change password.", "error")
        return redirect(url_for('profile'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM User WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if not user: # Should not happen
             flash("User not found.", "error"); return redirect(url_for('login'))

        # Verify current password using bcrypt
        if bcrypt.check_password_hash(user['password_hash'], current_password):
            # Hash the new password
            new_hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')

            # Update the database with the new hashed password
            update_cursor = conn.cursor()
            update_cursor.execute("UPDATE User SET password_hash = %s WHERE user_id = %s", (new_hashed_pw, user_id))
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


@app.route('/logout')
def logout():
    session.clear() # Clears user and admin sessions
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# --- ADMIN ROUTES ---

@app.route('/admin_login', methods=['GET'])
def admin_login():
    if session.get('is_admin'): return redirect(url_for('admin_dashboard'))
    session.pop('user', None)
    session.pop('user_name', None)
    # Use admin_login.html which now asks for email and password again
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
        # 1. Find user by email
        # Fetch the stored plain text password (in password_hash column)
        cursor.execute("SELECT user_id, name, password_hash FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user:
            # User email not found
            flash("Invalid credentials or not an admin.", "error")
            return redirect(url_for('admin_login'))

        # 2. !!! INSECURE: Plain text password comparison !!!
        if user['password_hash'] == password:
            # Password matches (plain text comparison)
            # 3. Check if this user is in the Admin table
            cursor.execute("SELECT admin_id FROM Admin WHERE user_id = %s", (user['user_id'],))
            admin_record = cursor.fetchone()

            if admin_record:
                # Successful Admin Login
                session.clear() # Clear any existing user session first
                session['is_admin'] = True
                session['admin_user_id'] = user['user_id']
                session['admin_user_name'] = user['name']
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                # User exists and password correct, but not listed in Admin table
                flash("Access denied. Not an authorized admin.", "error")
                return redirect(url_for('admin_login'))
        else:
            # Incorrect password (plain text comparison failed)
            flash("Invalid credentials or not an admin.", "error")
            return redirect(url_for('admin_login'))

    except mysql.connector.Error as err:
        app.logger.error(f"Database error during admin authentication: {err}")
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
    transports_with_schedules = {} # Use a dictionary to group schedules by transport

    search_term = request.args.get('search_term', '')
    filter_type = request.args.get('filter_type', '')
    filter_status = request.args.get('filter_status', '')

    try:
        # Base query for transports
        transport_query = "SELECT transport_id, type, name, operator, total_seats, status FROM Transport"
        transport_params = []
        transport_conditions = []

        # Add conditions based on filters
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

        # For each transport, fetch its schedules
        for transport in transports:
            transport_id = transport['transport_id']
            transports_with_schedules[transport_id] = {
                'details': transport,
                'schedules': []
            } # Initialize structure

            schedule_query = """
                SELECT
                    s.schedule_id, s.departure_time, s.arrival_time, s.duration_hours,
                    r.route_id, r.distance_km,
                    st_source.name AS source_station_name,
                    st_dest.name AS destination_station_name
                FROM Schedule s
                JOIN Route r ON s.route_id = r.route_id
                JOIN Station st_source ON r.source_id = st_source.station_id
                JOIN Station st_dest ON r.destination_id = st_dest.station_id
                WHERE s.transport_id = %s
                ORDER BY s.departure_time
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
                           transports_with_schedules=transports_with_schedules, # Pass the new structure
                           search_term=search_term,
                           filter_type=filter_type,
                           filter_status=filter_status)


# Add this new route in app.py

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
        # Fetch schedule details (optional, for context on the page)
        cursor.execute("""
            SELECT s.schedule_id, t.name as transport_name,
                   st_source.name AS source_station_name,
                   st_dest.name AS destination_station_name,
                   s.departure_time
            FROM Schedule s
            JOIN Transport t ON s.transport_id = t.transport_id
            JOIN Route r ON s.route_id = r.route_id
            JOIN Station st_source ON r.source_id = st_source.station_id
            JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE s.schedule_id = %s
        """, (schedule_id,))
        schedule_info = cursor.fetchone()

        if not schedule_info:
             flash(f"Schedule ID {schedule_id} not found.", "error")
             return redirect(url_for('admin_dashboard'))

        # Fetch bookings for this schedule, joining with User and Seat
        cursor.execute("""
            SELECT
                b.booking_id, b.booking_date, b.status, b.pnr_number,
                u.user_id, u.name AS user_name, u.email AS user_email,
                se.seat_id, se.seat_number, se.seat_class, se.price AS seat_price
            FROM Booking b
            JOIN User u ON b.user_id = u.user_id
            JOIN Seat se ON b.seat_id = se.seat_id
            WHERE b.schedule_id = %s
            ORDER BY b.booking_date DESC
        """, (schedule_id,))
        bookings = cursor.fetchall()

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching bookings for schedule {schedule_id}: {err}")
        flash("Failed to load booking data.", "error")
    finally:
        cursor.close()
        conn.close()

    # Create a new template 'admin_schedule_bookings.html'
    return render_template('admin_schedule_bookings.html',
                           bookings=bookings,
                           schedule_info=schedule_info,
                           schedule_id=schedule_id)

# Add this new route in app.py

@app.route('/admin/booking/<int:booking_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_specific_booking(booking_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        # Determine where to redirect - maybe back to the referring page if possible, or dashboard
        return redirect(request.referrer or url_for('admin_dashboard')) # Redirect back

    cursor = conn.cursor(dictionary=True)
    schedule_id = None # To redirect back to the correct schedule view
    try:
        conn.start_transaction()

        # 1. Get booking details (user_id, seat_id, current status, schedule_id)
        cursor.execute("""
            SELECT b.user_id, b.seat_id, b.status, b.schedule_id, s.price
            FROM Booking b
            JOIN Seat s ON b.seat_id = s.seat_id
            WHERE b.booking_id = %s
        """, (booking_id,))
        booking = cursor.fetchone()

        if not booking:
            flash(f"Booking ID {booking_id} not found.", "error")
            conn.rollback(); cursor.close(); conn.close()
            return redirect(request.referrer or url_for('admin_dashboard'))

        schedule_id = booking['schedule_id'] # Get schedule_id for redirect

        if booking['status'] != 'confirmed':
            flash(f"Booking ID {booking_id} is not in 'confirmed' state. Cannot cancel.", "warning")
            conn.rollback(); cursor.close(); conn.close()
            return redirect(url_for('admin_view_schedule_bookings', schedule_id=schedule_id))


        # 2. Perform cancellation logic
        user_id = booking['user_id']
        refund_amount = booking['price'] or 0.0 # Use seat price as refund amount

        # Update Booking status
        cursor.execute("UPDATE Booking SET status = 'cancelled_by_admin' WHERE booking_id = %s", (booking_id,))

        # Get next cancellation_id
        cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
        next_c_id = (cursor.fetchone()['max_id'] or 0) + 1

        # Insert into Cancellation table
        cursor.execute("""
            INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
            VALUES (%s, %s, NOW(), %s, 'completed')
        """, (next_c_id, booking_id, refund_amount))

        # Update User's refund balance
        cursor.execute("UPDATE User SET Refunds = Refunds + %s WHERE user_id = %s", (refund_amount, user_id))

        # 3. Commit
        conn.commit()
        flash(f"Booking ID {booking_id} cancelled and ₹{refund_amount:.2f} refunded successfully.", "success")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error cancelling booking {booking_id}: {err}")
        flash(f"Failed to cancel booking: {err}", "error")
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Unexpected error cancelling booking {booking_id}: {e}")
        flash("An unexpected error occurred during cancellation.", "error")
    finally:
        cursor.close()
        conn.close()

    # Redirect back to the bookings view for that schedule
    if schedule_id:
        return redirect(url_for('admin_view_schedule_bookings', schedule_id=schedule_id))
    else: # Fallback if schedule_id wasn't retrieved
        return redirect(url_for('admin_dashboard'))
    
# --- NEW ROUTES FOR EDITING SCHEDULE ---


@app.route('/admin/edit_schedule/<int:schedule_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_schedule(schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        new_departure_str = request.form.get('departure_time')
        new_arrival_str = request.form.get('arrival_time')

        try:
            # Basic validation (more robust validation needed for production)
            new_departure = datetime.datetime.strptime(new_departure_str, '%Y-%m-%dT%H:%M')
            new_arrival = datetime.datetime.strptime(new_arrival_str, '%Y-%m-%dT%H:%M')

            if new_arrival <= new_departure:
                flash("Arrival time must be after departure time.", "error")
                # Need to re-fetch schedule data to render form again with error
                cursor.execute("SELECT * FROM Schedule WHERE schedule_id = %s", (schedule_id,))
                schedule = cursor.fetchone()
                cursor.close(); conn.close()
                if not schedule: return redirect(url_for('admin_dashboard')) # Should not happen
                # Format existing times for datetime-local input value attribute
                schedule['departure_time_str'] = schedule['departure_time'].strftime('%Y-%m-%dT%H:%M')
                schedule['arrival_time_str'] = schedule['arrival_time'].strftime('%Y-%m-%dT%H:%M')
                return render_template('edit_schedule.html', schedule=schedule)


            # Calculate new duration (optional, could be auto-calculated or entered)
            duration = new_arrival - new_departure
            duration_hours = duration.total_seconds() / 3600

            cursor.execute("""
                UPDATE Schedule
                SET departure_time = %s, arrival_time = %s, duration_hours = %s
                WHERE schedule_id = %s
            """, (new_departure, new_arrival, duration_hours, schedule_id))
            conn.commit()
            flash(f"Schedule ID {schedule_id} updated successfully.", "success")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

        except ValueError:
            flash("Invalid date/time format. Please use YYYY-MM-DDTHH:MM.", "error")
            # Need to re-fetch schedule data to render form again with error
            cursor.execute("SELECT * FROM Schedule WHERE schedule_id = %s", (schedule_id,))
            schedule = cursor.fetchone()
            cursor.close(); conn.close()
            if not schedule: return redirect(url_for('admin_dashboard')) # Should not happen
            schedule['departure_time_str'] = schedule['departure_time'].strftime('%Y-%m-%dT%H:%M')
            schedule['arrival_time_str'] = schedule['arrival_time'].strftime('%Y-%m-%dT%H:%M')
            return render_template('edit_schedule.html', schedule=schedule)

        except mysql.connector.Error as err:
            conn.rollback()
            app.logger.error(f"Error updating schedule {schedule_id}: {err}")
            flash(f"Failed to update schedule: {err}", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))


    # --- GET Request ---
    try:
        # Fetch schedule details along with route/station names for context
        query = """
            SELECT
                s.schedule_id, s.departure_time, s.arrival_time,
                t.name as transport_name, t.type as transport_type,
                st_source.name AS source_station_name,
                st_dest.name AS destination_station_name
            FROM Schedule s
            JOIN Transport t ON s.transport_id = t.transport_id
            JOIN Route r ON s.route_id = r.route_id
            JOIN Station st_source ON r.source_id = st_source.station_id
            JOIN Station st_dest ON r.destination_id = st_dest.station_id
            WHERE s.schedule_id = %s
        """
        cursor.execute(query, (schedule_id,))
        schedule = cursor.fetchone()

        if not schedule:
            flash(f"Schedule ID {schedule_id} not found.", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

        # Format times for the datetime-local input type value attribute
        schedule['departure_time_str'] = schedule['departure_time'].strftime('%Y-%m-%dT%H:%M')
        schedule['arrival_time_str'] = schedule['arrival_time'].strftime('%Y-%m-%dT%H:%M')

        cursor.close(); conn.close()
        return render_template('edit_schedule.html', schedule=schedule)

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching schedule {schedule_id} for edit: {err}")
        flash("Failed to load schedule data for editing.", "error")
        if cursor and conn.is_connected(): cursor.close(); conn.close()
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/cancel_schedule/<int:schedule_id>', methods=['POST'])
@admin_required
def admin_cancel_schedule(schedule_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()

        # 1. Find active bookings for this schedule
        cursor.execute("""
            SELECT b.booking_id, b.user_id, b.seat_id, s.price
            FROM Booking b
            JOIN Seat s ON b.seat_id = s.seat_id
            WHERE b.schedule_id = %s AND b.status = 'confirmed'
        """, (schedule_id,))
        bookings_to_cancel = cursor.fetchall()

        cancelled_booking_count = 0
        total_refund_processed = 0.0
        processed_booking_ids = [] # Keep track of processed bookings

        # 2. Process cancellations for each booking
        for booking in bookings_to_cancel:
            booking_id = booking['booking_id']
            user_id = booking['user_id']
            # Use seat price as refund amount (assuming 100% refund)
            refund_amount = booking['price'] or 0.0 # Handle potential NULL price

            # Update Booking status
            cursor.execute("UPDATE Booking SET status = 'cancelled_by_admin' WHERE booking_id = %s", (booking_id,))

            # Get next cancellation_id (Consider AUTO_INCREMENT)
            cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
            max_c_id = cursor.fetchone()['max_id']
            next_c_id = (max_c_id or 0) + 1

            # Insert into Cancellation table
            cursor.execute("""
                INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
                VALUES (%s, %s, NOW(), %s, %s)
            """, (next_c_id, booking_id, refund_amount, 'completed')) # Assuming refund processed immediately

            # Update User's refund balance
            cursor.execute("UPDATE User SET Refunds = Refunds + %s WHERE user_id = %s", (refund_amount, user_id))

            processed_booking_ids.append(booking_id)
            cancelled_booking_count += 1
            total_refund_processed += float(refund_amount)

        # 3. --- REMOVED: Do NOT delete the schedule itself ---
        # cursor.execute("DELETE FROM Schedule WHERE schedule_id = %s", (schedule_id,))
        # --- END REMOVED ---

        # 4. Commit transaction
        conn.commit()

        if cancelled_booking_count > 0:
             flash(f"Processed {cancelled_booking_count} booking cancellations for Schedule ID {schedule_id} and refunded a total of ₹{total_refund_processed:.2f}. The schedule record remains but associated bookings are cancelled.", "success")
        else:
             flash(f"No active bookings found to cancel for Schedule ID {schedule_id}. The schedule record remains.", "info")


    except mysql.connector.Error as err:
        conn.rollback() # Rollback all changes on any error
        app.logger.error(f"Error cancelling bookings for schedule {schedule_id}: {err}")
        flash(f"Failed to cancel bookings for schedule: {err}", "error")
    except Exception as e: # Catch potential non-DB errors
        conn.rollback()
        app.logger.error(f"Unexpected error cancelling bookings for schedule {schedule_id}: {e}")
        flash("An unexpected error occurred during cancellation.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


# ... (Rest of the reverted app.py code) ...

# --- NEW ROUTES FOR EDITING PRICES ---
@app.route('/admin/prices/<int:transport_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_prices(transport_id):
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            updated_count = 0
            error_count = 0
            # Iterate through form data to find price updates
            for key, value in request.form.items():
                if key.startswith('price_'):
                    try:
                        seat_id = int(key.split('_')[1])
                        new_price = float(value)

                        if new_price < 0:
                             flash(f"Price for Seat ID {seat_id} cannot be negative.", "error")
                             error_count += 1
                             continue # Skip update for this seat

                        # IMPORTANT: Ensure the seat_id belongs to the correct transport_id
                        # to prevent unauthorized updates if someone crafts a POST request.
                        cursor.execute("UPDATE Seat SET price = %s WHERE seat_id = %s AND transport_id = %s",
                                       (new_price, seat_id, transport_id))
                        if cursor.rowcount > 0:
                             updated_count += 1

                    except (ValueError, IndexError):
                        app.logger.warning(f"Invalid data received in price form: key={key}, value={value}")
                        error_count += 1
                    except mysql.connector.Error as err:
                         conn.rollback() # Rollback on specific update error
                         app.logger.error(f"Error updating price for seat_id derived from {key}: {err}")
                         flash(f"Database error updating price for Seat ID {key.split('_')[1]}.", "error")
                         error_count += 1
                         # Decide if you want to stop all updates on first error or continue
                         # break # Stop processing further updates on error

            if error_count == 0:
                 conn.commit() # Commit all successful updates together
                 flash(f"{updated_count} seat prices updated successfully for Transport ID {transport_id}.", "success")
            else:
                conn.rollback() # Rollback all if any error occurred during processing
                flash(f"Some errors occurred. No prices were updated. Please check values.", "error")


        except Exception as e: # Catch potential general errors during form processing
             conn.rollback()
             app.logger.error(f"General error processing price updates for transport {transport_id}: {e}")
             flash("An unexpected error occurred while updating prices.", "error")

        finally:
            cursor.close(); conn.close()

        # Redirect back to dashboard or the prices page itself
        # Redirecting to dashboard might be simpler
        return redirect(url_for('admin_dashboard'))


    # --- GET Request ---
    try:
        # Fetch transport details for context
        cursor.execute("SELECT name, type FROM Transport WHERE transport_id = %s", (transport_id,))
        transport = cursor.fetchone()
        if not transport:
            flash(f"Transport ID {transport_id} not found.", "error")
            cursor.close(); conn.close()
            return redirect(url_for('admin_dashboard'))

        # Fetch seats for this transport
        cursor.execute("SELECT seat_id, seat_number, seat_class, price FROM Seat WHERE transport_id = %s ORDER BY seat_class, seat_number", (transport_id,))
        seats = cursor.fetchall()

        cursor.close(); conn.close()
        return render_template('edit_prices.html', transport=transport, seats=seats, transport_id=transport_id)

    except mysql.connector.Error as err:
        app.logger.error(f"Error fetching seats for transport {transport_id}: {err}")
        flash("Failed to load seat data for editing prices.", "error")
        if cursor and conn.is_connected(): cursor.close(); conn.close()
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_transport', methods=['POST'])
@admin_required
def admin_add_transport():
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed. Could not add transport.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor()
    try:
        type = request.form.get('type')
        name = request.form.get('name')
        operator = request.form.get('operator')
        total_seats = request.form.get('total_seats', type=int)
        status = request.form.get('status')

        if not all([type, name, operator, total_seats is not None, status]):
             flash("All fields are required to add a transport.", "error")
             return redirect(url_for('admin_dashboard'))
        if total_seats <= 0:
            flash("Total seats must be a positive number.", "error")
            return redirect(url_for('admin_dashboard'))

        # Get next transport ID (Consider AUTO_INCREMENT)
        cursor.execute("SELECT MAX(transport_id) AS max_id FROM Transport")
        result = cursor.fetchone()
        next_id = (result[0] or 0) + 1

        cursor.execute("""
            INSERT INTO Transport (transport_id, type, name, operator, total_seats, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (next_id, type, name, operator, total_seats, status))
        conn.commit()
        flash(f"Transport '{name}' added successfully!", "success")

    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error adding transport: {err}")
        flash(f"Failed to add transport: {err}", "error")
    except ValueError:
         flash("Invalid input for total seats (must be a number).", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_transport/<int:transport_id>', methods=['POST'])
@admin_required
def admin_delete_transport(transport_id):
    # Basic implementation - More robust checks needed in production
    # (e.g., ensure no active schedules/bookings depend on it)
    conn = get_db_connection()
    if not conn:
        flash("Database connection failed.", "error"); return redirect(url_for('admin_dashboard'))
    cursor = conn.cursor()
    try:
        # Ideally, check dependencies first (Routes, Seats, Schedules, Bookings)
        # For simplicity now, we rely on DB foreign key constraints to prevent deletion if used.
        cursor.execute("DELETE FROM Transport WHERE transport_id = %s", (transport_id,))
        conn.commit()
        if cursor.rowcount > 0: flash(f"Transport ID {transport_id} deleted.", "success")
        else: flash(f"Transport ID {transport_id} not found.", "warning")
    except mysql.connector.Error as err:
        conn.rollback()
        app.logger.error(f"Error deleting transport {transport_id}: {err}")
        if err.errno == 1451: # Foreign key constraint error code
             flash(f"Cannot delete Transport ID {transport_id}: It is referenced by other records (e.g., routes, schedules).", "error")
        else: flash(f"Failed to delete transport {transport_id}: {err}", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))

# --- TODO: Routes for Reschedule/Price changes ---


@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_user_id', None)
    session.pop('admin_user_name', None)
    flash('Admin logged out successfully.', 'success')
    return redirect(url_for('admin_login'))

# --- Main Execution ---
if __name__ == '__main__':
    import logging
    # Configure logging
    # In production, you might want to log to a file
    logging.basicConfig(level=logging.INFO) # Log INFO level and above (INFO, WARNING, ERROR, CRITICAL)
    # For development, DEBUG level might be useful:
    # logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True) # Keep debug=True for development for auto-reloading and traceback pages