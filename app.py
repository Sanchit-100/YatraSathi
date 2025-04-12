# File: app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify # Added jsonify
# Remove flask_bcrypt import if not used for hashing (as per current insecure implementation)
# from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG
import os # Needed for potential file uploads
import datetime # Import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
# bcrypt = Bcrypt(app) # Only if using bcrypt

# Configuration for profile picture uploads (optional)
# UPLOAD_FOLDER = 'static/profile_pics'
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        flash(f"Database connection error: {err}", "error")
        return None

@app.route('/')
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
             return render_template('login.html') # Stay on login page if DB connection failed

        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
            user = cursor.fetchone()

            # !!! SECURITY WARNING: Storing and comparing passwords in plain text is highly insecure.
            # Replace this with password hashing (e.g., using bcrypt) in a real application.
            # Example with bcrypt (requires installing flask-bcrypt):
            # if user and bcrypt.check_password_hash(user['password_hash'], password):
            if user and user['password_hash'] == password: # Current insecure check
                session['user'] = user['user_id']
                session['user_name'] = user['name'] # Store name for convenience
                flash('Logged in successfully!', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Invalid email or password.', 'error')

        except mysql.connector.Error as err:
            flash(f"Database error during login: {err}", "error")
        finally:
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

        # !!! SECURITY WARNING: Store hashed password, not plain text.
        # Example with bcrypt:
        # hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        hashed_pw = password  # Current insecure method

        conn = get_db_connection()
        if not conn:
             return render_template('register.html') # Stay on register page if DB connection failed

        try:
            check_cursor = conn.cursor(dictionary=True)
            check_cursor.execute("SELECT email, phone_number FROM User WHERE email = %s OR phone_number = %s", (email, phone))
            existing_user = check_cursor.fetchone()
            check_cursor.close()

            if existing_user:
                if existing_user['email'] == email:
                    flash('Email already exists.', 'error')
                else:
                    flash('Phone number already exists.', 'error')
                conn.close()
                return redirect(url_for('register'))

            insert_cursor = conn.cursor(dictionary=True)
            # It's generally safer to let the DB auto-increment IDs if possible.
            # Fetching MAX(id) can have race conditions. Assuming manual ID for now.
            insert_cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
            result = insert_cursor.fetchone()
            next_user_id = (result['max_id'] or 0) + 1

            insert_cursor.execute("""
                INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
                VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
            """, (next_user_id, name, email, hashed_pw, phone))

            conn.commit()
            insert_cursor.close()
            flash('Registered successfully. Please login.', 'success')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
             flash(f"Database error during registration: {err}", "error")
             # Rollback in case of error during insert
             if conn.is_connected():
                 conn.rollback()
        finally:
            if conn.is_connected():
                 conn.close()

    return render_template('register.html')


@app.route('/user/dashboard')
def user_dashboard():
    if 'user' not in session:
        flash('Please login to access the dashboard.', 'error')
        return redirect(url_for('login'))
    # Pass user name to dashboard template if needed
    # Pass username to the template
    return render_template('user_dashboard.html', user_name=session.get('user_name'), username=session.get('user_name'))

# --- NEW BOOKING ROUTE ---
@app.route('/booking', methods=['GET'])
def booking():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch distinct station names for dropdowns
    cursor.execute("SELECT DISTINCT name FROM Station ORDER BY name")
    stations = cursor.fetchall()

    # Fetch distinct active transport types for dropdown
    cursor.execute("SELECT DISTINCT type FROM Transport WHERE status = 'active' ORDER BY type")
    transport_types = cursor.fetchall()

    # --- Filtering Logic ---
    source_station_name = request.args.get('source_station')
    destination_station_name = request.args.get('destination_station')
    travel_date_str = request.args.get('travel_date')
    transport_type = request.args.get('transport_type')

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
        query += " AND st_source.name = %s"
        params.append(source_station_name)

    if destination_station_name:
        query += " AND st_dest.name = %s"
        params.append(destination_station_name)

    if travel_date_str:
        try:
            # Filter by date part only
            travel_date = datetime.datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            query += " AND DATE(s.departure_time) = %s"
            params.append(travel_date)
        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.")
            # Optionally, clear the date filter or handle the error differently

    if transport_type:
        query += " AND t.type = %s"
        params.append(transport_type)

    query += " ORDER BY s.departure_time"

    cursor.execute(query, tuple(params))
    available_transports = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('booking.html',
                           stations=stations,
                           transport_types=transport_types,
                           transports=available_transports,
                           # Pass filter values back to template to keep them selected
                           selected_source=source_station_name,
                           selected_destination=destination_station_name,
                           selected_date=travel_date_str,
                           selected_type=transport_type,
                           username=session.get('user_name')) # Pass username

# --- End New Booking Route ---


# --- Placeholder routes for specific booking pages ---
@app.route('/booking/flight')
def flight_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: Add logic for flight booking selection (e.g., pass schedule_id)
    flash("Flight booking page is under construction.")
    return render_template('flight_booking.html', username=session.get('user_name'))

@app.route('/booking/train')
def train_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: Add logic for train booking selection
    flash("Train booking page is under construction.")
    return render_template('train_booking.html', username=session.get('user_name'))

@app.route('/booking/bus')
def bus_booking():
    if 'user' not in session:
        return redirect(url_for('login'))
    # TODO: Add logic for bus booking selection
    flash("Bus booking page is under construction.")
    return render_template('bus_booking.html', username=session.get('user_name'))
# --- End Placeholder Routes ---


# --- Profile Routes ---
@app.route('/profile')
def profile():
    if 'user' not in session:
        flash('Please login to view your profile.', 'error')
        return redirect(url_for('login'))

    user_id = session['user']
    conn = get_db_connection()
    if not conn:
        # Redirect to dashboard or show error if DB fails
        flash("Could not connect to the database to load profile.", "error")
        return redirect(url_for('user_dashboard'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, name, email, phone_number, Refunds FROM User WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            flash("User profile not found.", "error")
            session.clear() # Log out user if profile doesn't exist
            return redirect(url_for('login'))

        return render_template('profile.html', user=user_data)

    except mysql.connector.Error as err:
        flash(f"Error loading profile: {err}", "error")
        return redirect(url_for('user_dashboard')) # Redirect on error
    finally:
        cursor.close()
        conn.close()

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('login'))

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
        conn.rollback() # Rollback on error
        flash(f"Error updating profile: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('profile'))


@app.route('/profile/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        return redirect(url_for('login'))

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

    cursor = conn.cursor(dictionary=True) # Use dictionary cursor to get hash easily
    try:
        cursor.execute("SELECT password_hash FROM User WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
             flash("User not found.", "error")
             return redirect(url_for('login'))

        # !!! SECURITY WARNING: Compare plain text passwords - highly insecure. Use hashing.
        # Example with bcrypt:
        # if bcrypt.check_password_hash(user['password_hash'], current_password):
        #     new_hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
        if user['password_hash'] == current_password: # Current insecure check
            # !!! SECURITY WARNING: Store hashed password.
            new_hashed_pw = new_password # Current insecure method

            update_cursor = conn.cursor()
            update_cursor.execute("UPDATE User SET password_hash = %s WHERE user_id = %s", (new_hashed_pw, user_id))
            conn.commit()
            update_cursor.close()
            flash("Password updated successfully!", "success")
        else:
            flash("Incorrect current password.", "error")

    except mysql.connector.Error as err:
        conn.rollback() # Rollback on error
        flash(f"Error changing password: {err}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('profile'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)