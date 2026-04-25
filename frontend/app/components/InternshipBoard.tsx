'use client';

import { useState, useMemo } from 'react';
import FilterBar from './FilterBar';
import InternshipCard from './InternshipCard';
import ApplyModal from './ApplyModal';

export interface Internship {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  postedAt: string;
  daysAgo: number;
  field: string;
}

const SEED_DATA: Internship[] = [
  { id: 1, title: 'Software Developer Intern', company: 'MapleTech', location: 'Toronto, ON', description: 'Work on real-world web apps with a Canadian tech leader. Collaborate with senior engineers on microservices architecture, CI/CD pipelines, and cloud deployments.', postedAt: '2 days ago', daysAgo: 2, field: 'Software & Engineering' },
  { id: 2, title: 'Marketing Intern', company: 'True North Media', location: 'Vancouver, BC', description: 'Assist in digital campaigns for Canadian brands. Create content strategies, manage social channels, and analyze campaign performance metrics.', postedAt: '1 day ago', daysAgo: 1, field: 'Marketing & Media' },
  { id: 3, title: 'Data Analyst Intern', company: 'Prairie Analytics', location: 'Calgary, AB', description: 'Analyze data trends for Canadian agriculture. Build dashboards, run statistical analyses, and present insights to stakeholders.', postedAt: '3 days ago', daysAgo: 3, field: 'Data & Analytics' },
  { id: 4, title: 'Finance Intern', company: 'Bank of Canada', location: 'Ottawa, ON', description: 'Support financial modeling and reporting. Assist with quarterly forecasts, regulatory compliance documentation, and risk assessment frameworks.', postedAt: 'about 5 hours ago', daysAgo: 0, field: 'Finance' },
  { id: 5, title: 'UX/UI Design Intern', company: 'RedLeaf Studios', location: 'Montreal, QC', description: 'Design user interfaces for Canadian startups. Conduct user research, build wireframes and prototypes, and collaborate with developers on implementation.', postedAt: 'about 6 hours ago', daysAgo: 0, field: 'Design' },
  { id: 6, title: 'Engineering Intern', company: 'Northern Rail', location: 'Winnipeg, MB', description: 'Work on infrastructure projects across Canada. Participate in structural analysis, project planning, and site inspections for national rail expansion.', postedAt: '4 days ago', daysAgo: 4, field: 'Software & Engineering' },
  { id: 7, title: 'Policy Research Intern', company: 'Gov of Canada', location: 'Ottawa, ON', description: 'Research and draft policy briefs. Analyze legislative proposals, compile evidence-based recommendations, and support parliamentary committee work.', postedAt: '1 day ago', daysAgo: 1, field: 'Policy & Government' },
  { id: 8, title: 'Environmental Science Intern', company: 'EcoCan', location: 'Victoria, BC', description: 'Assist with field research and reporting. Collect environmental samples, analyze water quality data, and contribute to conservation impact reports.', postedAt: '2 days ago', daysAgo: 2, field: 'Science & Environment' },
  { id: 9, title: 'Product Management Intern', company: 'StartupHub', location: 'Toronto, ON', description: 'Coordinate product launches and feedback. Manage feature backlogs, run sprint planning sessions, and gather user feedback for iteration.', postedAt: 'about 3 hours ago', daysAgo: 0, field: 'Product Management' },
  { id: 10, title: 'Journalism Intern', company: 'The Canadian Press', location: 'Toronto, ON', description: 'Write and edit news stories for national syndication. Cover breaking news, conduct interviews, and fact-check articles for publication.', postedAt: 'about 7 hours ago', daysAgo: 0, field: 'Journalism' },
];

interface InternshipBoardProps {
  trackedIds: Set<number>;
  onToggleTrack: (id: number) => void;
}

export default function InternshipBoard({ trackedIds, onToggleTrack }: InternshipBoardProps) {
  const [location, setLocation] = useState('All Locations');
  const [field, setField] = useState('All Fields');
  const [datePosted, setDatePosted] = useState('');
  const [applyJob, setApplyJob] = useState<Internship | null>(null);

  const filtered = useMemo(() => {
    return SEED_DATA.filter((job) => {
      if (location !== 'All Locations' && job.location !== location) return false;
      if (field !== 'All Fields' && job.field !== field) return false;
      if (datePosted) {
        const days = parseInt(datePosted, 10);
        if (job.daysAgo > days) return false;
      }
      return true;
    });
  }, [location, field, datePosted]);

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
            Latest Listings
          </h2>
          <hr className="newspaper-divider-thick flex-1" />
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-16 animate-fade-in">
            <p className="text-slate-400 text-sm">No internships match your filters.</p>
            <button
              onClick={() => { setLocation('All Locations'); setField('All Fields'); setDatePosted(''); }}
              className="mt-3 text-sm text-maple hover:underline"
            >
              Clear all filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
            {filtered.map((job, idx) => (
              <InternshipCard
                key={job.id}
                job={job}
                isTracked={trackedIds.has(job.id)}
                onTrack={() => onToggleTrack(job.id)}
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
