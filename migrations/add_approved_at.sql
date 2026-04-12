-- FR-0012: Add approved_at column and reporting indexes to RFPO table
-- Run against Azure PostgreSQL: psql $DATABASE_URL -f migrations/add_approved_at.sql

-- 1. Add approved_at column
ALTER TABLE rfpo ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;

-- 2. Create index on approved_at
CREATE INDEX IF NOT EXISTS idx_rfpo_approved_at ON rfpo (approved_at);

-- 3. Composite indexes for reporting performance
CREATE INDEX IF NOT EXISTS idx_rfpo_status_created ON rfpo (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rfpo_status_approved ON rfpo (status, approved_at DESC);

-- 4. Backfill approved_at for existing approved RFPOs (use updated_at as approximation)
UPDATE rfpo SET approved_at = updated_at
WHERE status = 'Approved' AND approved_at IS NULL;
