-- Migration 002: Add country and is_active fields for expanded crawler
-- Run this in your Supabase SQL Editor

-- Add new columns
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country text DEFAULT 'Unknown';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true;

-- Index for country filtering
CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs (country);

-- Index for active jobs
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs (is_active);

-- Composite index for the most common frontend query
CREATE INDEX IF NOT EXISTS idx_jobs_active_country_seen ON jobs (is_active, country, first_seen DESC);
