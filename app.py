# File: app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
# Make sure flask_bcrypt is installed (pip install flask-bcrypt) or remove if not using hashing yet
# from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG
from datetime import datetime # Import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
# bcrypt = Bcrypt(app) # Uncomment if using Bcrypt

def get_db_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database Connection Error: {err}")
        # In a real app, you might want to handle this more gracefully
        # For now, we'll let it propagate or return None
        flash("Database connection failed. Please try again later.", "error")
        return None

def get_cursor(conn):
    """Returns a dictionary cursor for the given connection."""
    if conn:
        return conn.cursor(dictionary=True)
    return None

@app.route('/')
def landing():
    """Renders the landing page."""
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'] # Plain text password check

        conn = get_db_connection()
        cursor = get_cursor(conn)

        if not cursor:
            return render_template('login.html') # DB connection failed

        try:
            cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
            user = cursor.fetchone()

            # IMPORTANT: Replace plain text check with hashed password check in production
            # Example using bcrypt:
            # if user and bcrypt.check_password_hash(user['password_hash'], password):
            if user and user['password_hash'] == password: # Current plain text check [cite: YatraSathi/app.py]
                session['user_id'] = user['user_id']
                session['user_name'] = user['name']
                flash('Login successful!', 'success')
                return redirect(url_for('user_dashboard'))
            else:
                flash('Invalid email or password.', 'error')

        except mysql.connector.Error as err:
            flash(f"Database error during login: {err}", 'error')
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']

        # IMPORTANT: Hash the password before storing it in production
        # hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        hashed_pw = password # Storing plain text for now [cite: YatraSathi/app.py]

        conn = get_db_connection()
        cursor = get_cursor(conn)

        if not cursor:
            return render_template('register.html') # DB connection failed

        try:
            # Check if user already exists
            cursor.execute("SELECT user_id FROM User WHERE email = %s OR phone_number = %s", (email, phone))
            existing_user = cursor.fetchone()

            if existing_user:
                flash('User already exists with this email or phone number.', 'error')
                return redirect(url_for('register'))

            # Get next user ID (ensure atomicity in a high-concurrency environment)
            cursor.execute("SELECT MAX(user_id) AS max_id FROM User")
            result = cursor.fetchone()
            next_user_id = (result['max_id'] or 0) + 1

            # Insert new user
            cursor.execute("""
                INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds)
                VALUES (%s, %s, %s, %s, %s, 'regular', NOW(), 0.00)
            """, (next_user_id, name, email, hashed_pw, phone))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            conn.rollback() # Rollback changes on error
            flash(f"Database error during registration: {err}", 'error')
            return redirect(url_for('register'))
        finally:
             if cursor: cursor.close()
             if conn: conn.close()

    return render_template('register.html')


@app.route('/user/dashboard')
def user_dashboard():
    """Displays the user dashboard."""
    if 'user_id' not in session:
         flash('Please log in to access the dashboard.', 'error')
         return redirect(url_for('login'))
    # Pass username to the template
    return render_template('user_dashboard.html', username=session.get('user_name'))


@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/booking')
def booking():
    """Displays the main booking search page."""
    if 'user_id' not in session:
        flash('Please log in to book transport.', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = get_cursor(conn)

    if not cursor:
        # Handle case where DB connection failed - render template with error?
         return render_template('booking.html', username=session.get('user_name'), stations=[], transport_types=[], transports=[], error="Could not connect to database.")


    stations = []
    transport_types = []
    transports = []
    selected_source = request.args.get('source_station')
    selected_destination = request.args.get('destination_station')
    selected_date_str = request.args.get('travel_date')
    selected_type = request.args.get('transport_type')

    try:
        # Fetch distinct stations for dropdowns
        cursor.execute("SELECT DISTINCT name FROM Station ORDER BY name")
        stations = cursor.fetchall()

        # Fetch distinct transport types for dropdown
        cursor.execute("SELECT DISTINCT type FROM Transport ORDER BY type")
        transport_types = cursor.fetchall()

        # Build the base query
        query = """
            SELECT
                sch.schedule_id, sch.departure_time, sch.arrival_time, sch.duration_hours,
                t.transport_id, t.name AS transport_name, t.type AS transport_type, t.operator,
                r.route_id, r.distance_km,
                s_source.name AS source_station_name,
                s_dest.name AS destination_station_name,
                MIN(se.price) AS min_price
            FROM Schedule sch
            JOIN Transport t ON sch.transport_id = t.transport_id
            JOIN Route r ON sch.route_id = r.route_id
            JOIN Station s_source ON r.source_id = s_source.station_id
            JOIN Station s_dest ON r.destination_id = s_dest.station_id
            LEFT JOIN Seat se ON t.transport_id = se.transport_id
            WHERE t.status = 'active'
        """
        params = []

        # Add filters based on user input
        if selected_source:
            query += " AND s_source.name = %s"
            params.append(selected_source)
        if selected_destination:
            query += " AND s_dest.name = %s"
            params.append(selected_destination)
        if selected_date_str:
            query += " AND DATE(sch.departure_time) = %s"
            params.append(selected_date_str)
        if selected_type:
            query += " AND t.type = %s"
            params.append(selected_type)

        query += """
            GROUP BY sch.schedule_id, t.transport_id, r.route_id, s_source.name, s_dest.name
            ORDER BY sch.departure_time
        """

        cursor.execute(query, tuple(params))
        transports = cursor.fetchall()

    except mysql.connector.Error as err:
         flash(f"Database error fetching booking info: {err}", 'error')
         # Optionally return an error template or redirect
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('booking.html',
                           username=session.get('user_name'),
                           stations=stations,
                           transport_types=transport_types,
                           transports=transports,
                           selected_source=selected_source,
                           selected_destination=selected_destination,
                           selected_date=selected_date_str,
                           selected_type=selected_type)


# --- Placeholders for Specific Booking Pages ---
@app.route('/flight-booking')
@app.route('/flight-booking/<int:schedule_id>')
def flight_booking(schedule_id=None):
    if 'user_id' not in session: return redirect(url_for('login'))
    # Add actual booking logic here, fetch schedule details etc.
    return render_template('flight_booking.html', schedule_id=schedule_id, username=session.get('user_name'))

@app.route('/train-booking')
@app.route('/train-booking/<int:schedule_id>')
def train_booking(schedule_id=None):
    if 'user_id' not in session: return redirect(url_for('login'))
    # Add actual booking logic here
    return render_template('train_booking.html', schedule_id=schedule_id, username=session.get('user_name'))

@app.route('/bus-booking')
@app.route('/bus-booking/<int:schedule_id>')
def bus_booking(schedule_id=None):
    if 'user_id' not in session: return redirect(url_for('login'))
    # Add actual booking logic here
    return render_template('bus_booking.html', schedule_id=schedule_id, username=session.get('user_name'))


# --- Profile Management Routes ---
@app.route('/profile')
def profile():
    """Displays the user's profile page."""
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = get_cursor(conn)

    if not cursor:
        # Redirect or show error if DB connection failed
        flash("Could not retrieve profile data.", "error")
        return redirect(url_for('user_dashboard'))

    user_data = None
    try:
        cursor.execute("SELECT user_id, name, email, phone_number, user_type, created_at, Refunds FROM User WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
             flash("User profile not found.", "error")
             session.clear() # Log out user if profile doesn't exist
             return redirect(url_for('login'))

    except mysql.connector.Error as err:
        flash(f"Database error retrieving profile: {err}", 'error')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # Render even if user_data is None (template should handle this)
    return render_template('profile.html', user=user_data, username=session.get('user_name'))


@app.route('/update_profile', methods=['POST'])
def update_profile():
    """Handles updates to user profile details."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    name = request.form['name']
    email = request.form['email']
    phone = request.form['phone']

    conn = get_db_connection()
    cursor = get_cursor(conn)

    if not cursor:
         flash("Database connection failed.", "error")
         return redirect(url_for('profile'))

    try:
        # Optional: Check if new email/phone already exists for another user
        cursor.execute("SELECT user_id FROM User WHERE (email = %s OR phone_number = %s) AND user_id != %s", (email, phone, user_id))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("Email or phone number already in use by another account.", "error")
            return redirect(url_for('profile'))

        # Update user details
        cursor.execute("""
            UPDATE User
            SET name = %s, email = %s, phone_number = %s
            WHERE user_id = %s
        """, (name, email, phone, user_id))
        conn.commit()

        # Update session username if name changed
        session['user_name'] = name
        flash('Profile updated successfully!', 'success')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error updating profile: {err}", 'error')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return redirect(url_for('profile'))


@app.route('/change_password', methods=['POST'])
def change_password():
    """Handles user password change requests."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))

    if not new_password: # Basic validation
         flash('New password cannot be empty.', 'error')
         return redirect(url_for('profile'))


    conn = get_db_connection()
    cursor = get_cursor(conn)

    if not cursor:
        flash("Database connection failed.", "error")
        return redirect(url_for('profile'))

    try:
        # Get current password hash
        cursor.execute("SELECT password_hash FROM User WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
             flash('User not found.', 'error')
             return redirect(url_for('login')) # Log out if user doesn't exist

        # IMPORTANT: Replace plain text check with hash check
        # if bcrypt.check_password_hash(user['password_hash'], current_password):
        if user['password_hash'] == current_password: # Current plain text check [cite: YatraSathi/app.py]
             # Hash the new password before storing
             # new_hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
             new_hashed_pw = new_password # Storing plain text for now [cite: YatraSathi/app.py]

             cursor.execute("UPDATE User SET password_hash = %s WHERE user_id = %s", (new_hashed_pw, user_id))
             conn.commit()
             flash('Password updated successfully!', 'success')
        else:
             flash('Incorrect current password.', 'error')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Database error changing password: {err}", 'error')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return redirect(url_for('profile'))

# --- NEW Cancellation Routes ---

@app.route('/cancellation')
def cancellation():
    """Displays the cancellation management page with active bookings and history."""
    if 'user_id' not in session:
        flash('Please log in to manage your bookings.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()
    cursor = get_cursor(conn)

    if not cursor:
        flash("Database connection failed.", "error")
        return render_template('cancellation.html', username=session.get('user_name'), active_bookings=[], cancellations=[])

    active_bookings = []
    cancellations = []

    try:
        # Fetch Active Bookings (status is 'confirmed' or similar, NOT 'cancelled')
        # Query joins multiple tables to get comprehensive details for display
        active_query = """
            SELECT
                b.booking_id, b.pnr_number, b.booking_date, b.status,
                sch.departure_time, sch.arrival_time,
                t.name AS transport_name, t.type AS transport_type,
                s_source.name AS source_station_name,
                s_dest.name AS destination_station_name,
                se.seat_number, se.seat_class
            FROM Booking b
            JOIN Schedule sch ON b.schedule_id = sch.schedule_id
            JOIN Transport t ON sch.transport_id = t.transport_id
            JOIN Route r ON sch.route_id = r.route_id
            JOIN Station s_source ON r.source_id = s_source.station_id
            JOIN Station s_dest ON r.destination_id = s_dest.station_id
            JOIN Seat se ON b.seat_id = se.seat_id
            WHERE b.user_id = %s AND b.status != 'cancelled'
            ORDER BY sch.departure_time DESC
        """
        cursor.execute(active_query, (user_id,))
        active_bookings = cursor.fetchall()

        # Fetch Cancellation History
        # Query joins multiple tables to get comprehensive details for display
        cancelled_query = """
            SELECT
                c.cancellation_id, c.cancellation_date, c.refund_amount, c.refund_status,
                b.pnr_number, b.booking_date,
                sch.departure_time, sch.arrival_time,
                t.name AS transport_name, t.type AS transport_type,
                s_source.name AS source_station_name,
                s_dest.name AS destination_station_name
            FROM Cancellation c
            JOIN Booking b ON c.booking_id = b.booking_id
            JOIN Schedule sch ON b.schedule_id = sch.schedule_id
            JOIN Transport t ON sch.transport_id = t.transport_id
            JOIN Route r ON sch.route_id = r.route_id
            JOIN Station s_source ON r.source_id = s_source.station_id
            JOIN Station s_dest ON r.destination_id = s_dest.station_id
            WHERE b.user_id = %s
            ORDER BY c.cancellation_date DESC
        """
        cursor.execute(cancelled_query, (user_id,))
        cancellations = cursor.fetchall()

    except mysql.connector.Error as err:
        flash(f"Database error fetching booking/cancellation data: {err}", 'error')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return render_template('cancellation.html',
                           username=session.get('user_name'),
                           active_bookings=active_bookings,
                           cancellations=cancellations)


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    """Handles the cancellation request for a specific booking."""
    if 'user_id' not in session:
        flash('Please log in to cancel bookings.', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db_connection()

    if not conn:
        flash("Database connection failed, cannot cancel booking.", "error")
        return redirect(url_for('cancellation'))

    cursor = get_cursor(conn)

    if not cursor:
        flash("Failed to get database cursor, cannot cancel booking.", "error")
        if conn: conn.close()
        return redirect(url_for('cancellation'))

    try:
        conn.start_transaction()

        # 1. Check if the booking exists, belongs to the user, and is not already cancelled
        cursor.execute("""
            SELECT booking_id, status
            FROM Booking
            WHERE booking_id = %s AND user_id = %s
        """, (booking_id, user_id))
        booking = cursor.fetchone()

        if not booking:
            flash("Booking not found or you do not have permission to cancel it.", "error")
            conn.rollback() # Important: Rollback even if no changes were made yet
            return redirect(url_for('cancellation'))

        if booking['status'] == 'cancelled':
            flash("This booking has already been cancelled.", "info")
            conn.rollback()
            return redirect(url_for('cancellation'))

        # 2. Update booking status to 'cancelled'
        cursor.execute("""
            UPDATE Booking SET status = 'cancelled' WHERE booking_id = %s
        """, (booking_id,))

        # 3. Insert into Cancellation table
        # Get next cancellation ID
        cursor.execute("SELECT MAX(cancellation_id) AS max_id FROM Cancellation")
        result = cursor.fetchone()
        next_cancellation_id = (result['max_id'] or 0) + 1

        # Insert cancellation record with 'not-confirmed' refund status
        # Refund amount is initially 0.00; actual refund calculation would happen later
        # based on rules (e.g., departure time vs cancellation time) from Project_Overview.pdf [cite: 14, 34]
        cursor.execute("""
            INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status)
            VALUES (%s, %s, NOW(), %s, %s)
        """, (next_cancellation_id, booking_id, 0.00, 'not-confirmed')) # Initial refund amount 0

        # 4. Commit transaction
        conn.commit()
        flash('Booking cancelled successfully.', 'success')

    except mysql.connector.Error as err:
        conn.rollback() # Rollback on any database error during the process
        flash(f"Database error during cancellation: {err}", 'error')
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    return redirect(url_for('cancellation'))


# --- Main Execution ---
if __name__ == '__main__':
    app.run(debug=True) # Turn off debug mode in production