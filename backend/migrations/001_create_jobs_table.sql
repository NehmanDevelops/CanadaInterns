-- Migration 001: Create jobs table for Canadian internship listings
-- Run this in your Supabase SQL Editor

create table if not exists jobs (
  id text primary key,
  title text,
  company text,
  location text,
  url text,
  ats_platform text,
  posted_at timestamptz,
  first_seen timestamptz default now(),
  is_canadian boolean default true
);

-- Index for fast lookups by first_seen (latest jobs endpoint)
create index if not exists idx_jobs_first_seen on jobs (first_seen desc);

-- Index for location filtering
create index if not exists idx_jobs_location on jobs (location);

-- Index for ATS platform filtering
create index if not exists idx_jobs_ats_platform on jobs (ats_platform);
