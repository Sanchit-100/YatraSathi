CREATE DATABASE test;
USE test;
CREATE TABLE Transport ( transport_id INT PRIMARY KEY, type VARCHAR(50),name    VARCHAR(100), operator VARCHAR(100), total_seats  INT, status VARCHAR(50) );



CREATE TABLE Station ( station_id INT PRIMARY KEY, name VARCHAR(100),city VARCHAR(100), type      VARCHAR(50) );



CREATE TABLE Route ( route_id INT PRIMARY KEY, transport_id   INT, station_id     INT,

    source_id      INT, destination_id INT,distance_km    DECIMAL(10,2), FOREIGN KEY (transport_id) REFERENCES Transport(transport_id), FOREIGN KEY (station_id) REFERENCES Station(station_id), FOREIGN KEY (source_id) REFERENCES Station(station_id), FOREIGN KEY (destination_id) REFERENCES Station(station_id)

);



-- Table: Seat

CREATE TABLE Seat (

    seat_id     INT PRIMARY KEY,

    transport_id INT,

    seat_number VARCHAR(10),

    seat_class  VARCHAR(50),

    price       DECIMAL(10,2),

    FOREIGN KEY (transport_id) REFERENCES Transport(transport_id)

);



-- Table: Schedule

CREATE TABLE Schedule (

    schedule_id     INT PRIMARY KEY,

    transport_id    INT,

    route_id        INT,

    departure_time  DATETIME,

    arrival_time    DATETIME,

    duration_hours  DECIMAL(5,2),

    FOREIGN KEY (transport_id) REFERENCES Transport(transport_id),

    FOREIGN KEY (route_id) REFERENCES Route(route_id)

);



-- Table: User

CREATE TABLE User (

    user_id       INT PRIMARY KEY,

    name          VARCHAR(100),

    email         VARCHAR(100),

    password_hash VARCHAR(255),

    phone_number  VARCHAR(20),

    user_type     VARCHAR(50),

    created_at    DATETIME,

    Refunds       DECIMAL(10,2)

);



-- Table: Booking

CREATE TABLE Booking (

    booking_id   INT PRIMARY KEY,

    user_id      INT,

    schedule_id  INT,

    seat_id      INT,

    booking_date DATETIME,

    status       VARCHAR(50),

    pnr_number   VARCHAR(50),

    FOREIGN KEY (user_id) REFERENCES User(user_id),

    FOREIGN KEY (schedule_id) REFERENCES Schedule(schedule_id),

    FOREIGN KEY (seat_id) REFERENCES Seat(seat_id)

);



-- Table: Feedback

CREATE TABLE Feedback (

    feedback_id INT PRIMARY KEY,

    user_id     INT,

    booking_id  INT,

    rating      INT,

    review      TEXT,

    submitted_at DATETIME,

    FOREIGN KEY (user_id) REFERENCES User(user_id),

    FOREIGN KEY (booking_id) REFERENCES Booking(booking_id)

);



-- Table: Payment

CREATE TABLE Payment (

    payment_id     INT PRIMARY KEY,

    booking_id     INT,

    amount         DECIMAL(10,2),

    payment_method VARCHAR(50),

    transaction_id VARCHAR(100),

    payment_status VARCHAR(50),

    FOREIGN KEY (booking_id) REFERENCES Booking(booking_id)

);



-- Table: Cancellation

CREATE TABLE Cancellation (

    cancellation_id  INT PRIMARY KEY,

    booking_id       INT,

    cancellation_date DATETIME,

    refund_amount    DECIMAL(10,2),

    refund_status    VARCHAR(50),

    FOREIGN KEY (booking_id) REFERENCES Booking(booking_id)

);



-- Table: Admin

CREATE TABLE Admin (

    admin_id INT PRIMARY KEY,

    user_id  INT,

    role     VARCHAR(50),

    FOREIGN KEY (user_id) REFERENCES User(user_id)

);