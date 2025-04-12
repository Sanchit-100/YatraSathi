# File: app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify # Added jsonify
from flask_bcrypt import Bcrypt
import mysql.connector
from config import DB_CONFIG
import datetime # Import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'
bcrypt = Bcrypt(app)


def get_db_connection():
    # Ensure dictionary=True for cursor results
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
        cursor = conn.cursor(dictionary=True) # Ensure dictionary=True

        cursor.execute("SELECT * FROM User WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and user['password_hash'] == password: # Assuming plain text password for now
            session['user'] = user['user_id']
            session['user_name'] = user['name'] # Store user name in session
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

        hashed_pw = password  # Store plain text for now as per login logic

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
    # Pass username to the template
    return render_template('user_dashboard.html', username=session.get('user_name'))

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


@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_id = session['user']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, email, phone_number, user_type, created_at, Refunds FROM User WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user_data:
        flash("User data not found.")
        return redirect(url_for('user_dashboard'))

    # TODO: Create a proper profile.html template to display this data
    # For now, just render the placeholder
    return render_template('profile.html', user=user_data, username=session.get('user_name'))


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)