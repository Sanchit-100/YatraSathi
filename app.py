from flask import Flask, render_template, jsonify
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/routes', methods=['GET'])
def get_routes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Simplified query that only gets transport data
    query = """
    SELECT transport_id, type, name, operator, total_seats, status
    FROM Transport
    LIMIT 10
    """
    
    cursor.execute(query)
    transports = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(transports)

if __name__ == '__main__':
    app.run(debug=True)