INSERT INTO Transport (transport_id, type, name, operator, total_seats, status) VALUES
(1, 'bus', 'Express Rider 101', 'City Transit Co.', 45, 'active'),
(2, 'bus', 'Metro Connect 202', 'Regional Bus Lines', 50, 'active'),
(3, 'train', 'Silver Arrow Express', 'National Railways', 200, 'active'),
(4, 'train', 'Coastal Commuter', 'Coast Rail Services', 180, 'active'),
(5, 'flight', 'Sky Connect 300', 'Air Express', 120, 'active'),
(6, 'flight', 'Cloud Cruiser 405', 'Sky Routes Inc.', 150, 'active'),
(7, 'bus', 'Night Rider 303', 'City Transit Co.', 40, 'maintenance'),
(8, 'train', 'Mountain Explorer', 'National Railways', 220, 'active'),
(9, 'flight', 'Star Flight 505', 'Air Express', 180, 'active'),
(10, 'bus', 'City Hopper 404', 'Regional Bus Lines', 35, 'active');

INSERT INTO Station (station_id, name, city, type) VALUES
(1, 'Central Station', 'New York', 'hub'),
(2, 'Union Terminal', 'Chicago', 'hub'),
(3, 'Pacific Station', 'Los Angeles', 'hub'),
(4, 'Mountain View Depot', 'Denver', 'terminal'),
(5, 'Coastal Terminal', 'Miami', 'terminal'),
(6, 'Airport International', 'Dallas', 'airport'),
(7, 'Sky Harbor', 'Phoenix', 'airport'),
(8, 'Bus Terminal North', 'Boston', 'bus_station'),
(9, 'South Station', 'Atlanta', 'hub'),
(10, 'West End Terminal', 'Seattle', 'terminal');

INSERT INTO Route (route_id, transport_id, station_id, source_id, destination_id, distance_km) VALUES
(1, 1, 1, 1, 8, 350.50),
(2, 1, 8, 8, 1, 350.50),
(3, 2, 2, 2, 4, 1500.75),
(4, 2, 4, 4, 2, 1500.75),
(5, 3, 1, 1, 2, 1200.00),
(6, 3, 2, 2, 1, 1200.00),
(7, 4, 2, 2, 3, 2800.50),
(8, 4, 3, 3, 2, 2800.50),
(9, 5, 6, 6, 7, 1800.25),
(10, 5, 7, 7, 6, 1800.25),
(11, 6, 6, 6, 3, 2200.75),
(12, 6, 3, 3, 6, 2200.75),
(13, 7, 8, 8, 9, 1600.50),
(14, 7, 9, 9, 8, 1600.50),
(15, 8, 1, 1, 3, 3900.00),
(16, 8, 3, 3, 1, 3900.00),
(17, 9, 7, 7, 3, 850.25),
(18, 9, 3, 3, 7, 850.25),
(19, 10, 9, 9, 10, 4500.75),
(20, 10, 10, 10, 9, 4500.75);

INSERT INTO Seat (seat_id, transport_id, seat_number, seat_class, price) VALUES
-- Bus seats (Economy)
(1, 1, 'A1', 'economy', 50.00),
(2, 1, 'A2', 'economy', 50.00),
(3, 1, 'B1', 'economy', 50.00),
(4, 1, 'B2', 'economy', 50.00),
-- Train seats (Economy and Business)
(5, 3, 'C1', 'business', 120.00),
(6, 3, 'C2', 'business', 120.00),
(7, 3, 'D1', 'economy', 80.00),
(8, 3, 'D2', 'economy', 80.00),
-- Flight seats (First, Business, Economy)
(9, 5, 'F1', 'first', 500.00),
(10, 5, 'F2', 'first', 500.00),
(11, 5, 'B1', 'business', 300.00),
(12, 5, 'B2', 'business', 300.00),
(13, 5, 'E1', 'economy', 200.00),
(14, 5, 'E2', 'economy', 200.00),
-- Additional seats for various transports
(15, 2, 'A1', 'economy', 45.00),
(16, 2, 'A2', 'economy', 45.00),
(17, 4, 'C1', 'business', 150.00),
(18, 4, 'C2', 'business', 150.00),
(19, 6, 'F1', 'first', 600.00),
(20, 6, 'F2', 'first', 600.00),
(21, 7, 'A1', 'economy', 40.00),
(22, 7, 'A2', 'economy', 40.00),
(23, 8, 'C1', 'business', 200.00),
(24, 8, 'C2', 'business', 200.00),
(25, 9, 'F1', 'first', 550.00),
(26, 9, 'F2', 'first', 550.00),
(27, 10, 'A1', 'economy', 35.00),
(28, 10, 'A2', 'economy', 35.00),
(29, 1, 'C1', 'economy', 55.00),
(30, 1, 'C2', 'economy', 55.00),
(31, 3, 'E1', 'economy', 85.00),
(32, 3, 'E2', 'economy', 85.00),
(33, 5, 'G1', 'economy', 210.00),
(34, 5, 'G2', 'economy', 210.00),
(35, 2, 'B1', 'economy', 45.00),
(36, 2, 'B2', 'economy', 45.00),
(37, 4, 'D1', 'economy', 90.00),
(38, 4, 'D2', 'economy', 90.00),
(39, 6, 'E1', 'business', 350.00),
(40, 6, 'E2', 'business', 350.00);

INSERT INTO Schedule (schedule_id, transport_id, route_id, departure_time, arrival_time, duration_hours) VALUES
(1, 1, 1, '2025-02-15 08:00:00', '2025-02-15 12:00:00', 4.00),
(2, 3, 5, '2025-02-15 09:00:00', '2025-02-15 14:00:00', 5.00),
(3, 5, 9, '2025-02-15 10:00:00', '2025-02-15 12:30:00', 2.50),
(4, 2, 3, '2025-02-15 11:00:00', '2025-02-15 17:00:00', 6.00),
(5, 4, 7, '2025-02-15 13:00:00', '2025-02-15 20:00:00', 7.00),
(6, 6, 11, '2025-02-15 14:00:00', '2025-02-15 17:00:00', 3.00),
(7, 7, 13, '2025-02-15 15:00:00', '2025-02-15 20:00:00', 5.00),
(8, 8, 15, '2025-02-15 16:00:00', '2025-02-16 00:00:00', 8.00),
(9, 9, 17, '2025-02-15 17:00:00', '2025-02-15 19:00:00', 2.00),
(10, 10, 19, '2025-02-15 18:00:00', '2025-02-16 02:00:00', 8.00);

INSERT INTO User (user_id, name, email, password_hash, phone_number, user_type, created_at, Refunds) VALUES
(1, 'John Smith', 'john.smith@email.com', 'hash1', '555-0101', 'regular', '2024-01-01 10:00:00', 0.00),
(2, 'Mary Johnson', 'mary.j@email.com', 'hash2', '555-0102', 'premium', '2024-01-02 11:00:00', 100.00),
(3, 'Robert Brown', 'robert.b@email.com', 'hash3', '555-0103', 'regular', '2024-01-03 12:00:00', 0.00),
(4, 'Patricia Davis', 'pat.d@email.com', 'hash4', '555-0104', 'premium', '2024-01-04 13:00:00', 50.00),
(5, 'Michael Wilson', 'michael.w@email.com', 'hash5', '555-0105', 'regular', '2024-01-05 14:00:00', 0.00);

INSERT INTO Booking (booking_id, user_id, schedule_id, seat_id, booking_date, status, pnr_number) VALUES
(1, 1, 1, 1, '2025-02-01 10:00:00', 'confirmed', 'PNR001'),
(2, 2, 2, 5, '2025-02-02 11:00:00', 'confirmed', 'PNR002'),
(3, 3, 3, 9, '2025-02-03 12:00:00', 'cancelled', 'PNR003'),
(4, 4, 4, 15, '2025-02-04 13:00:00', 'confirmed', 'PNR004'),
(5, 5, 5, 17, '2025-02-05 14:00:00', 'confirmed', 'PNR005');

INSERT INTO Feedback (feedback_id, user_id, booking_id, rating, review, submitted_at) VALUES
(1, 1, 1, 4, 'Great service, very punctual', '2025-02-15 16:00:00'),
(2, 2, 2, 5, 'Excellent journey, very comfortable', '2025-02-15 19:00:00'),
(3, 4, 4, 3, 'Good service but could be better', '2025-02-15 20:00:00');

INSERT INTO Payment (payment_id, booking_id, amount, payment_method, transaction_id, payment_status) VALUES
(1, 1, 50.00, 'credit_card', 'TXN001', 'completed'),
(2, 2, 120.00, 'debit_card', 'TXN002', 'completed'),
(3, 3, 500.00, 'credit_card', 'TXN003', 'refunded'),
(4, 4, 45.00, 'online_wallet', 'TXN004', 'completed'),
(5, 5, 150.00, 'credit_card', 'TXN005', 'completed');

INSERT INTO Cancellation (cancellation_id, booking_id, cancellation_date, refund_amount, refund_status) VALUES
(1, 3, '2025-02-04 10:00:00', 450.00, 'completed');

INSERT INTO Admin (admin_id, user_id, role) VALUES
(1, 2, 'supervisor');
