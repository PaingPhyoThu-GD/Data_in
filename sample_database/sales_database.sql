-- Sample Sales Database Export
-- Generated for AI Services Hub Database Converter

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL
);

INSERT INTO customers (customer_id, name, email, city) VALUES
(101, 'Aung Kyaw', 'aungkyaw@example.com', 'Yangon'),
(102, 'Thida Win', 'thidawin@example.com', 'Mandalay'),
(103, 'Min Thu', 'minthu@example.com', 'Naypyidaw'),
(104, 'Su Su Hlaing', 'susu@example.com', 'Bago');

CREATE TABLE sales_table (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    order_date TEXT NOT NULL
);

INSERT INTO sales_table (order_id, customer_id, product_name, category, quantity, unit_price, total_amount, order_date) VALUES
(1001, 101, 'Mechanical Gaming Keyboard', 'Electronics', 1, 89.99, 89.99, '2026-11-01'),
(1002, 102, 'Wireless Ergonomic Mouse', 'Electronics', 2, 29.50, 59.00, '2026-11-02'),
(1003, 101, 'USB-C Fast Charging Hub', 'Accessories', 3, 24.00, 72.00, '2026-11-03'),
(1004, 103, 'Noise Cancelling Headphones', 'Audio', 1, 149.00, 149.00, '2026-11-04'),
(1005, 104, 'Ultra-wide IPS Monitor 34-inch', 'Displays', 1, 399.00, 399.00, '2026-11-05');
