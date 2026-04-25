'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import FilterBar from './FilterBar';
import InternshipCard from './InternshipCard';
import ApplyModal from './ApplyModal';

export interface Internship {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  ats_platform: string;
  posted_at: string;
  first_seen: string;
  is_canadian: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

interface InternshipBoardProps {
  trackedIds: Set<string>;
  onToggleTrack: (id: string, job?: Internship) => void;
}

export default function InternshipBoard({ trackedIds, onToggleTrack }: InternshipBoardProps) {
  const [jobs, setJobs] = useState<Internship[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [location, setLocation] = useState('All Locations');
  const [field, setField] = useState('All Fields');
  const [datePosted, setDatePosted] = useState('');
  const [applyJob, setApplyJob] = useState<Internship | null>(null);

  // Fetch jobs from backend
  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (location !== 'All Locations') params.set('location', location.split(',')[0].trim());
      if (field !== 'All Fields') params.set('field', field);
      params.set('limit', '200');

      const res = await fetch(`${API_BASE}/api/jobs?${params.toString()}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      setJobs(data.jobs || []);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch jobs:', err);
      setError('Could not load listings. Make sure the backend is running.');
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [location, field]);

  // Initial fetch + refetch when filters change
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(fetchJobs, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  // Client-side date filter
  const filtered = useMemo(() => {
    if (!datePosted) return jobs;
    const days = parseInt(datePosted, 10);
    const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    return jobs.filter((job) => {
      const seen = new Date(job.first_seen || job.posted_at);
      return seen >= cutoff;
    });
  }, [jobs, datePosted]);

  // Relative time helper
  function timeAgo(dateStr: string): string {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `about ${mins} min ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `about ${hours} hour${hours > 1 ? 's' : ''} ago`;
    const days = Math.floor(hours / 24);
    return `${days} day${days > 1 ? 's' : ''} ago`;
  }

  return (
    <>
      <FilterBar
        location={location}
        field={field}
        datePosted={datePosted}
        onLocationChange={setLocation}
        onFieldChange={setField}
        onDateChange={setDatePosted}
        resultCount={filtered.length}
      />

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" id="listings">
        {/* Section header */}
        <div className="flex items-center gap-3 mb-6">
          <hr className="newspaper-divider-thick flex-1" />
          <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 whitespace-nowrap">
            {loading ? 'Loading…' : 'Live Listings'}
          </h2>
          <hr className="newspaper-divider-thick flex-1" />
        </div>

        {/* Error state */}
        {error && (
          <div className="text-center py-12 animate-fade-in">
            <p className="text-sm text-maple font-medium mb-2">{error}</p>
            <button onClick={fetchJobs} className="text-sm text-slate-500 hover:text-slate-700 underline">
              Retry
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && !error && (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-slate-200 border-t-maple rounded-full animate-spin" />
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-16 animate-fade-in">
            <p className="text-slate-400 text-sm">No internships match your filters.</p>
            <button
              onClick={() => { setLocation('All Locations'); setField('All Fields'); setDatePosted(''); }}
              className="mt-3 text-sm text-maple hover:underline"
            >
              Clear all filters
            </button>
          </div>
        )}

        {/* Job grid */}
        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
            {filtered.map((job, idx) => (
              <InternshipCard
                key={job.id}
                job={{ ...job, postedAt: timeAgo(job.posted_at || job.first_seen) }}
                isTracked={trackedIds.has(job.id)}
                onTrack={() => onToggleTrack(job.id, job)}
                onApply={() => setApplyJob(job)}
                index={idx}
              />
            ))}
          </div>
        )}
      </section>

      {/* Apply modal */}
      {applyJob && (
        <ApplyModal job={applyJob} onClose={() => setApplyJob(null)} />
      )}
    </>
  );
}
