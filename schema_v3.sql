-- ============================================================================
-- PlantMind AI V3 - Dispatch & Reporting Engine
-- Database Schema Extension
-- Adds 3 new tables: dispatch_log, mis_report_log, order_status_log
-- Alters orders table with dispatch tracking columns
-- ============================================================================

-- ============================================================================
-- ALTER existing tables for V3
-- ============================================================================

-- Add dispatch tracking columns to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatch_email_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatch_sent_at TIMESTAMP;

-- Expand allowed status values (orders.status now includes 'dispatched' and 'awaiting_material')
-- Note: No CHECK constraint exists on orders.status — it uses application-level validation
-- Status values: new / needs_review / scheduled / in_production / awaiting_material / completed / dispatched

-- ============================================================================
-- Table 13: dispatch_log
-- Tracks every dispatch email attempt and outcome
-- ============================================================================

CREATE TABLE IF NOT EXISTS dispatch_log (
    dispatch_log_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    customer_email VARCHAR(200),
    email_subject TEXT,
    email_body TEXT,
    send_status VARCHAR(30) DEFAULT 'queued',
    -- Values: queued / sent / failed
    attempts INTEGER DEFAULT 0,
    error_details TEXT,
    triggered_by VARCHAR(50) DEFAULT 'v3_dispatch_job',
    -- Values: v3_dispatch_job / manual_trigger / api
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispatch_log_order ON dispatch_log(order_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_status ON dispatch_log(send_status);
CREATE INDEX IF NOT EXISTS idx_dispatch_log_created ON dispatch_log(created_at DESC);

-- ============================================================================
-- Table 14: mis_report_log
-- Tracks every daily MIS report generation and delivery
-- ============================================================================

CREATE TABLE IF NOT EXISTS mis_report_log (
    mis_report_log_id SERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    owner_email VARCHAR(200),
    email_subject TEXT,
    report_body TEXT,
    send_status VARCHAR(30) DEFAULT 'queued',
    -- Values: queued / sent / failed
    attempts INTEGER DEFAULT 0,
    error_details TEXT,
    triggered_by VARCHAR(50) DEFAULT 'v3_mis_report_job',
    -- Values: v3_mis_report_job / manual_trigger / api
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mis_report_log_date ON mis_report_log(report_date DESC);
CREATE INDEX IF NOT EXISTS idx_mis_report_log_status ON mis_report_log(send_status);

-- ============================================================================
-- Table 15: order_status_log
-- Full audit trail of every order status change
-- ============================================================================

CREATE TABLE IF NOT EXISTS order_status_log (
    log_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    change_source VARCHAR(50) NOT NULL DEFAULT 'system',
    -- Values: system / manual / v1_processor / v2_processor / v3_processor / supervisor / office_staff
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_status_log_order ON order_status_log(order_id);
CREATE INDEX IF NOT EXISTS idx_order_status_log_created ON order_status_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_status_log_new_status ON order_status_log(new_status);

-- ============================================================================
-- V3 Trigger: Auto-log order status changes
-- ============================================================================

CREATE OR REPLACE FUNCTION log_order_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log when status actually changes
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO order_status_log (order_id, old_status, new_status, change_source, notes)
        VALUES (
            NEW.order_id,
            OLD.status,
            NEW.status,
            'system',
            'Automatic status change detected'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_status_log ON orders;
CREATE TRIGGER trg_order_status_log
    AFTER UPDATE ON orders
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION log_order_status_change();

-- ============================================================================
-- V3 Trigger: Auto-update dispatch tracking on orders
-- ============================================================================

CREATE OR REPLACE FUNCTION update_order_dispatch_tracking()
RETURNS TRIGGER AS $$
BEGIN
    -- When order transitions to 'dispatched', set dispatch tracking fields
    IF NEW.status = 'dispatched' AND (OLD.status IS DISTINCT FROM 'dispatched') THEN
        NEW.dispatch_email_sent = TRUE;
        NEW.dispatch_sent_at = CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_dispatch_tracking ON orders;
CREATE TRIGGER trg_order_dispatch_tracking
    BEFORE UPDATE ON orders
    FOR EACH ROW
    WHEN (NEW.status = 'dispatched' AND OLD.status IS DISTINCT FROM 'dispatched')
    EXECUTE FUNCTION update_order_dispatch_tracking();

-- ============================================================================
-- V3 Performance Indexes
-- ============================================================================

-- Index for finding completed orders ready for dispatch
CREATE INDEX IF NOT EXISTS idx_orders_completed_not_dispatched
ON orders(order_id)
WHERE status = 'completed' AND (dispatch_email_sent = FALSE OR dispatch_email_sent IS NULL);

-- Index for MIS report date uniqueness queries
CREATE INDEX IF NOT EXISTS idx_mis_report_date_unique
ON mis_report_log(report_date, triggered_by);

-- Show created tables
-- \dt dispatch_log
-- \dt mis_report_log
-- \dt order_status_log
