-- PlantMind AI - Database Schema
-- Version 1 - Smart Order Intake System (Corrected to match specification)

-- Connect to database
-- \c plantmind;

-- Drop tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS email_log CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Table 1: customers
-- Stores all customers discovered from emails. Auto-created when new sender found.
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: orders
-- Core order record. Created by Order Extraction Agent.
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id) ON DELETE CASCADE,
    product_name VARCHAR(300) NOT NULL,
    quantity INTEGER NOT NULL,
    required_delivery_date DATE,
    special_instructions TEXT,
    status VARCHAR(30) DEFAULT 'new', 
    -- Values: new / needs_review / scheduled / in_production / completed
    priority VARCHAR(20) DEFAULT 'normal', 
    -- normal / urgent / rush
    source_email_id INTEGER REFERENCES email_log(email_id),
    estimated_hours_actual DECIMAL(8,2), 
    -- For tracking estimate vs actual time
    batch_number VARCHAR(50), 
    -- For lot tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: email_log
-- Every email the system sees — processed or skipped.
CREATE TABLE email_log (
    email_id SERIAL PRIMARY KEY,
    gmail_message_id VARCHAR(200) UNIQUE NOT NULL,
    direction VARCHAR(10) DEFAULT 'in',
    -- Values: in / out
    from_address VARCHAR(200),
    to_address VARCHAR(200),
    subject TEXT,
    body_summary TEXT,
    attachment_name VARCHAR(200),
    filter_decision VARCHAR(20),
    -- Values: process / skip
    processing_status VARCHAR(30),
    -- Values: success / flagged / error / skipped
    linked_order_id INTEGER,  -- Will reference orders(order_id) after constraint added
    error_details TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 4: users
-- Login credentials for all roles. V1 only uses office_staff role.
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL,
    -- Values: owner / office_staff / supervisor / store
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Now add foreign key constraints that were forward-referenced
ALTER TABLE orders ADD CONSTRAINT fk_orders_source_email
    FOREIGN KEY (source_email_id) REFERENCES email_log(email_id) ON DELETE SET NULL;

ALTER TABLE email_log ADD CONSTRAINT fk_email_log_linked_order
    FOREIGN KEY (linked_order_id) REFERENCES orders(order_id) ON DELETE SET NULL;

-- Create indexes for better query performance
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_email_log_processing_status ON email_log(processing_status);
CREATE INDEX idx_email_log_gmail_message_id ON email_log(gmail_message_id);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_email_log_processed_at ON email_log(processed_at);

-- Default users are created by src.database.init_db() to ensure valid bcrypt hashes.

-- Table 5: order_notes
-- Internal notes and timeline for each order
CREATE TABLE order_notes (
    note_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    note_type VARCHAR(50) NOT NULL DEFAULT 'general',
    -- Values: general / status_change / customer_call / internal / system
    note_text TEXT NOT NULL,
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_order_notes_order ON order_notes(order_id);
CREATE INDEX idx_order_notes_created ON order_notes(created_at DESC);

-- Show created tables
-- \dt

-- Show table structure
-- \d customers
-- \d orders
-- \d email_log
-- \d users
