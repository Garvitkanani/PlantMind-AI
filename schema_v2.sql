-- ============================================================================
-- PlantMind AI V2 - Production & Inventory Brain
-- Database Schema Extension
-- Adds 6 new tables for inventory, suppliers, products, machines, scheduling
-- ============================================================================

-- Table 5: suppliers
-- Stores supplier contact information for auto-reorder
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(200) NOT NULL,
    phone VARCHAR(20),
    material_supplied VARCHAR(200),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_suppliers_email ON suppliers(email);
CREATE INDEX idx_suppliers_active ON suppliers(is_active);

-- Table 6: raw_materials
-- Tracks inventory levels and reorder triggers
CREATE TABLE IF NOT EXISTS raw_materials (
    material_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(100),
    current_stock_kg DECIMAL(10,2) NOT NULL DEFAULT 0,
    reorder_level_kg DECIMAL(10,2) NOT NULL,
    reorder_quantity_kg DECIMAL(10,2) NOT NULL,
    unit_price_per_kg DECIMAL(10,2),
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE SET NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure stock never goes negative
    CONSTRAINT chk_non_negative_stock CHECK (current_stock_kg >= 0),
    -- Ensure reorder levels are positive
    CONSTRAINT chk_positive_reorder_level CHECK (reorder_level_kg > 0),
    CONSTRAINT chk_positive_reorder_qty CHECK (reorder_quantity_kg > 0)
);

CREATE INDEX idx_raw_materials_name ON raw_materials(name);
CREATE INDEX idx_raw_materials_supplier ON raw_materials(supplier_id);
CREATE INDEX idx_raw_materials_low_stock ON raw_materials(current_stock_kg, reorder_level_kg) 
    WHERE current_stock_kg <= reorder_level_kg;

-- Table 7: products
-- Maps product names to their material requirements and machine cycle times
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(300) NOT NULL UNIQUE,
    description TEXT,
    material_id INTEGER REFERENCES raw_materials(material_id) ON DELETE RESTRICT,
    material_required_per_unit_kg DECIMAL(8,4) NOT NULL,
    machine_cycle_time_seconds INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure positive material requirement
    CONSTRAINT chk_positive_material CHECK (material_required_per_unit_kg > 0),
    -- Ensure positive cycle time
    CONSTRAINT chk_positive_cycle_time CHECK (machine_cycle_time_seconds > 0)
);

CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_material ON products(material_id);
CREATE INDEX idx_products_active ON products(is_active);

-- Table 8: machines
-- Tracks injection moulding machines and their status
CREATE TABLE IF NOT EXISTS machines (
    machine_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    model VARCHAR(100),
    status VARCHAR(30) DEFAULT 'available',
    -- available / running / maintenance / offline
    current_order_id INTEGER REFERENCES orders(order_id),
    last_maintenance_date DATE,
    next_scheduled_maintenance DATE,
    maintenance_interval_hours INTEGER DEFAULT 720, -- Default 30 days (720 hours)
    total_runtime_hours DECIMAL(10,2) DEFAULT 0, -- Cumulative runtime for maintenance tracking
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Valid status values
    CONSTRAINT chk_machine_status CHECK (status IN ('available', 'running', 'maintenance', 'offline'))
);

CREATE INDEX idx_machines_status ON machines(status);
CREATE INDEX idx_machines_current_order ON machines(current_order_id);
CREATE INDEX idx_machines_active ON machines(is_active);

-- Table 9: production_schedule
-- Links orders to machines with scheduling information
CREATE TABLE IF NOT EXISTS production_schedule (
    schedule_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES machines(machine_id) ON DELETE SET NULL,
    estimated_start TIMESTAMP NOT NULL,
    estimated_end TIMESTAMP NOT NULL,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    status VARCHAR(30) DEFAULT 'scheduled',
    delay_alert_sent BOOLEAN DEFAULT FALSE,
    delay_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Valid status values
    CONSTRAINT chk_schedule_status CHECK (status IN ('scheduled', 'in_production', 'completed', 'cancelled', 'delayed')),
    -- Ensure estimated end is after estimated start
    CONSTRAINT chk_estimated_times CHECK (estimated_end > estimated_start),
    -- One schedule per order
    CONSTRAINT unique_order_schedule UNIQUE (order_id)
);

CREATE INDEX idx_production_schedule_order ON production_schedule(order_id);
CREATE INDEX idx_production_schedule_machine ON production_schedule(machine_id);
CREATE INDEX idx_production_schedule_status ON production_schedule(status);
CREATE INDEX idx_production_schedule_dates ON production_schedule(estimated_start, estimated_end);

-- Table 10: production_progress
-- Tracks supervisor updates on production progress
CREATE TABLE IF NOT EXISTS production_progress (
    progress_id SERIAL PRIMARY KEY,
    schedule_id INTEGER REFERENCES production_schedule(schedule_id) ON DELETE CASCADE,
    pieces_completed INTEGER NOT NULL, -- Good pieces only
    pieces_defective INTEGER DEFAULT 0, -- Scrap/defective pieces
    total_pieces INTEGER NOT NULL, -- Original order quantity
    completion_percentage DECIMAL(5, 2) GENERATED ALWAYS AS (
        CASE 
            WHEN total_pieces > 0 THEN ROUND((pieces_completed::DECIMAL / total_pieces) * 100, 2)
            ELSE 0
        END
    ) STORED,
    scrap_reason VARCHAR(200), -- Reason for scrap (if any)
    batch_number VARCHAR(50), -- Batch number for production
    updated_by INTEGER REFERENCES users(user_id),
    notes VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure pieces completed doesn't exceed total
    CONSTRAINT chk_progress_not_exceed_total CHECK (pieces_completed <= total_pieces),
    -- Ensure non-negative progress
    CONSTRAINT chk_non_negative_progress CHECK (pieces_completed >= 0),
    -- Ensure non-negative defective count
    CONSTRAINT chk_non_negative_defective CHECK (pieces_defective >= 0)
);

CREATE INDEX idx_production_progress_schedule ON production_progress(schedule_id);
CREATE INDEX idx_production_progress_created ON production_progress(created_at);

-- Table 11: reorder_log
-- Logs all supplier reorders (auto and manual)
CREATE TABLE IF NOT EXISTS reorder_log (
    reorder_id SERIAL PRIMARY KEY,
    material_id INTEGER NOT NULL REFERENCES raw_materials(material_id) ON DELETE RESTRICT,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE SET NULL,
    quantity_kg DECIMAL(10,2) NOT NULL,
    triggered_by VARCHAR(50) NOT NULL, -- 'auto_order', 'manual_store', 'system_alert'
    order_id INTEGER REFERENCES orders(order_id) ON DELETE SET NULL,
    email_sent_to VARCHAR(200),
    email_subject TEXT,
    email_body TEXT,
    status VARCHAR(30) DEFAULT 'pending',
    delivery_expected_by DATE,
    actual_delivery_date DATE,
    delivery_quantity_kg DECIMAL(10,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Valid status values
    CONSTRAINT chk_reorder_status CHECK (status IN ('pending', 'ordered', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    -- Valid trigger types
    CONSTRAINT chk_trigger_type CHECK (triggered_by IN ('auto_order', 'manual_store', 'system_alert', 'scheduled')),
    -- Ensure positive quantity
    CONSTRAINT chk_positive_reorder_qty CHECK (quantity_kg > 0)
);

CREATE INDEX idx_reorder_log_material ON reorder_log(material_id);
CREATE INDEX idx_reorder_log_supplier ON reorder_log(supplier_id);
CREATE INDEX idx_reorder_log_status ON reorder_log(status);
CREATE INDEX idx_reorder_log_order ON reorder_log(order_id);
CREATE INDEX idx_reorder_log_created ON reorder_log(created_at);

-- ============================================================================
-- V2 Helper Functions and Triggers
-- ============================================================================

-- Function to update raw_materials.last_updated timestamp
CREATE OR REPLACE FUNCTION update_material_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update last_updated on raw_materials
DROP TRIGGER IF EXISTS trg_material_timestamp ON raw_materials;
CREATE TRIGGER trg_material_timestamp
    BEFORE UPDATE ON raw_materials
    FOR EACH ROW
    EXECUTE FUNCTION update_material_timestamp();

-- Function to update machine status when production_schedule changes
CREATE OR REPLACE FUNCTION update_machine_on_schedule_change()
RETURNS TRIGGER AS $$
BEGIN
    -- If schedule is in_production, mark machine as running
    IF NEW.status = 'in_production' AND NEW.machine_id IS NOT NULL THEN
        UPDATE machines 
        SET status = 'running', 
            current_order_id = NEW.order_id,
            updated_at = CURRENT_TIMESTAMP
        WHERE machine_id = NEW.machine_id;
    
    -- If schedule is completed or cancelled, free up the machine
    ELSIF NEW.status IN ('completed', 'cancelled') AND NEW.machine_id IS NOT NULL THEN
        UPDATE machines 
        SET status = 'available', 
            current_order_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE machine_id = NEW.machine_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to sync machine status with production schedule
DROP TRIGGER IF EXISTS trg_sync_machine_status ON production_schedule;
CREATE TRIGGER trg_sync_machine_status
    AFTER UPDATE ON production_schedule
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION update_machine_on_schedule_change();

-- Function to update order status when production schedule changes
CREATE OR REPLACE FUNCTION update_order_on_schedule_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Map schedule status to order status
    IF NEW.status = 'scheduled' THEN
        UPDATE orders SET status = 'scheduled' WHERE order_id = NEW.order_id;
    ELSIF NEW.status = 'in_production' THEN
        UPDATE orders SET status = 'in_production' WHERE order_id = NEW.order_id;
    ELSIF NEW.status = 'completed' THEN
        UPDATE orders SET status = 'completed' WHERE order_id = NEW.order_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to sync order status with production schedule
DROP TRIGGER IF EXISTS trg_sync_order_status ON production_schedule;
CREATE TRIGGER trg_sync_order_status
    AFTER UPDATE ON production_schedule
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION update_order_on_schedule_change();

-- ============================================================================
-- V2 Seed Data for Testing
-- ============================================================================

-- Insert sample suppliers
INSERT INTO suppliers (name, email, phone, material_supplied, address, is_active)
VALUES 
    ('Rajesh Polymers', 'orders@rajeshpolymers.com', '+91-9876543210', 'HDPE Granules', 'Ahmedabad, Gujarat', TRUE),
    ('Gujarat Plastics', 'sales@gujaratplastics.com', '+91-9876543211', 'PP Granules', 'Surat, Gujarat', TRUE),
    ('Mumbai Chemicals', 'supply@mumbaichem.com', '+91-9876543212', 'PVC Compound', 'Mumbai, Maharashtra', TRUE)
ON CONFLICT DO NOTHING;

-- Insert sample raw materials
INSERT INTO raw_materials (name, type, current_stock_kg, reorder_level_kg, reorder_quantity_kg, unit_price_per_kg, supplier_id)
VALUES 
    ('HDPE Granules', 'High-Density Polyethylene', 500.00, 100.00, 500.00, 85.50, 1),
    ('PP Granules', 'Polypropylene', 300.00, 75.00, 400.00, 92.00, 2),
    ('PVC Compound', 'Polyvinyl Chloride', 200.00, 50.00, 300.00, 110.00, 3)
ON CONFLICT DO NOTHING;

-- Insert sample products (HDPE Cap 50mm)
INSERT INTO products (name, description, material_id, material_required_per_unit_kg, machine_cycle_time_seconds, is_active)
SELECT 
    'HDPE Container Cap 50mm',
    'Standard 50mm HDPE cap for containers',
    material_id,
    0.012,  -- 12 grams = 0.012 kg per cap
    8,      -- 8 seconds per piece cycle time
    TRUE
FROM raw_materials WHERE name = 'HDPE Granules'
ON CONFLICT DO NOTHING;

-- Insert sample machines
INSERT INTO machines (name, model, status, last_maintenance_date, next_scheduled_maintenance, notes, is_active)
VALUES 
    ('Machine-01', 'Toshiba IS220GN', 'available', '2025-03-15', '2025-06-15', 'Primary machine for HDPE caps', TRUE),
    ('Machine-02', 'Toshiba IS180GN', 'available', '2025-04-01', '2025-07-01', 'Secondary machine', TRUE),
    ('Machine-03', 'JSW J220AD', 'available', '2025-04-10', '2025-07-10', 'For PP products', TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Table 12: stock_log
-- Audit log for all material stock changes (manual updates, production usage, deliveries)
-- ============================================================================

CREATE TABLE IF NOT EXISTS stock_log (
    log_id SERIAL PRIMARY KEY,
    material_id INTEGER NOT NULL REFERENCES raw_materials(material_id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(order_id) ON DELETE SET NULL,
    change_type VARCHAR(50) NOT NULL,  -- 'manual_update', 'production_usage', 'delivery', 'wastage', 'returns'
    quantity_before_kg DECIMAL(10,2) NOT NULL,
    quantity_after_kg DECIMAL(10,2) NOT NULL,
    change_amount_kg DECIMAL(10,2) NOT NULL,  -- positive for add, negative for subtract
    reason VARCHAR(200),
    updated_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_log_material ON stock_log(material_id);
CREATE INDEX idx_stock_log_created ON stock_log(updated_at DESC);
CREATE INDEX idx_stock_log_change_type ON stock_log(change_type);

-- ============================================================================
-- V2 Indexes for Performance
-- ============================================================================

-- Composite index for production schedule queries
CREATE INDEX IF NOT EXISTS idx_schedule_status_machine 
ON production_schedule(status, machine_id) 
WHERE status IN ('scheduled', 'in_production');

-- Index for active machines
CREATE INDEX IF NOT EXISTS idx_machines_available 
ON machines(machine_id) 
WHERE status = 'available' AND is_active = TRUE;

-- Index for pending reorders
CREATE INDEX IF NOT EXISTS idx_reorder_pending 
ON reorder_log(reorder_id) 
WHERE status IN ('pending', 'ordered', 'confirmed');

-- Index for low stock materials
CREATE INDEX IF NOT EXISTS idx_materials_need_reorder 
ON raw_materials(material_id, current_stock_kg, reorder_level_kg) 
WHERE current_stock_kg <= reorder_level_kg;
