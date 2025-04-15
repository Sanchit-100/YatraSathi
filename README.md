# YatraSathi - Transportation Booking Platform

## Problem Statement
The transportation booking landscape is fragmented, with separate platforms for buses, trains, and flights. YatraSathi aims to provide a unified solution where users can search, compare, and book different transportation options in one place, simplifying travel planning and ticket management.

## 🚀 Features

- **Multi-modal Transportation**: Book buses, trains, and flights in a single platform
- **Smart Search**: Find the best routes between any two destinations
- **Seat Selection**: Interactive seat selection for all transport types
- **Secure Payments**: Multiple payment options with transaction security
- **Booking Management**: View, modify, or cancel bookings
- **User Profiles**: Track booking history and manage preferences
- **Feedback System**: Rate and review your travel experiences
- **Refund Processing**: Automated refund calculations for cancellations

## 💻 Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript 
- **Backend**: Python, Flask
- **Database**: MySQL
- **Version Control**: Git & GitHub

## 📊 Database Schema

The platform uses a relational database with the following key entities:
- Transport (buses, trains, flights)
- Stations & Routes
- Schedules & Seats
- Users & Bookings
- Payments & Cancellations
- Admin & Feedback

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/YatraSathi.git
   cd YatraSathi
   ```

2. **Set up the database**
   ```bash
   mysql -u root -p < schema.sql
   mysql -u root -p < insert_into.sql
   ```

3. **Configure database connection**
   ```bash
   # Copy the sample config file and update with your credentials
   copy config.sample.py config.py
   # Edit config.py with your database username and password
   ```

4. **Install Python dependencies**
   ```bash
   pip install flask mysql-connector-python
   ```

### Running the Application

1. **Start the Flask server**
   ```bash
   python app.py
   ```

2. **Access the application**
   - Open your browser and navigate to: http://localhost:5000

## 📂 Project Structure

```
YatraSathi/
├── app.py                 # Flask application entry point
├── config.sample.py       # Sample database configuration
├── schema.sql             # Database schema
├── insert_into.sql        # Sample data
├── static/                # Static assets
│   ├── css/               # Stylesheets
│   │   └── style.css
│   └── js/                # JavaScript files
│       └── script.js
└── templates/             # HTML templates
    └── index.html         # Main page
```

## 🔍 Use Cases

1. **Traveler Planning a Trip**
   - Search for transportation options between cities
   - Compare prices, durations, and departure times
   - Book the preferred option with seat selection

2. **Business Traveler**
   - Quick booking process for frequent routes
   - Access to booking history for expense reporting
   - Real-time updates on schedule changes

3. **Transportation Operators** (Admin)
   - Manage vehicle information and schedules
   - Track bookings and occupancy rates
   - Process refunds and handle feedback

4. **Customer Support**
   - Access user booking details
   - Process modification requests
   - Handle cancellations and refunds

*YatraSathi - Your Transportation Companion*
