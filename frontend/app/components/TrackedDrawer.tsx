'use client';

import { Internship } from './InternshipBoard';

interface TrackedDrawerProps {
  open: boolean;
  onClose: () => void;
  trackedIds: Set<number>;
  allJobs: Internship[];
  onRemove: (id: number) => void;
}

// Flat seed reference for lookup — in production this would come from state/context
const SEED_DATA: Internship[] = [
  { id: 1, title: 'Software Developer Intern', company: 'MapleTech', location: 'Toronto, ON', description: '', postedAt: '2 days ago', daysAgo: 2, field: 'Software & Engineering' },
  { id: 2, title: 'Marketing Intern', company: 'True North Media', location: 'Vancouver, BC', description: '', postedAt: '1 day ago', daysAgo: 1, field: 'Marketing & Media' },
  { id: 3, title: 'Data Analyst Intern', company: 'Prairie Analytics', location: 'Calgary, AB', description: '', postedAt: '3 days ago', daysAgo: 3, field: 'Data & Analytics' },
  { id: 4, title: 'Finance Intern', company: 'Bank of Canada', location: 'Ottawa, ON', description: '', postedAt: 'about 5 hours ago', daysAgo: 0, field: 'Finance' },
  { id: 5, title: 'UX/UI Design Intern', company: 'RedLeaf Studios', location: 'Montreal, QC', description: '', postedAt: 'about 6 hours ago', daysAgo: 0, field: 'Design' },
  { id: 6, title: 'Engineering Intern', company: 'Northern Rail', location: 'Winnipeg, MB', description: '', postedAt: '4 days ago', daysAgo: 4, field: 'Software & Engineering' },
  { id: 7, title: 'Policy Research Intern', company: 'Gov of Canada', location: 'Ottawa, ON', description: '', postedAt: '1 day ago', daysAgo: 1, field: 'Policy & Government' },
  { id: 8, title: 'Environmental Science Intern', company: 'EcoCan', location: 'Victoria, BC', description: '', postedAt: '2 days ago', daysAgo: 2, field: 'Science & Environment' },
  { id: 9, title: 'Product Management Intern', company: 'StartupHub', location: 'Toronto, ON', description: '', postedAt: 'about 3 hours ago', daysAgo: 0, field: 'Product Management' },
  { id: 10, title: 'Journalism Intern', company: 'The Canadian Press', location: 'Toronto, ON', description: '', postedAt: 'about 7 hours ago', daysAgo: 0, field: 'Journalism' },
];

export default function TrackedDrawer({ open, onClose, trackedIds, onRemove }: TrackedDrawerProps) {
  if (!open) return null;

  const tracked = SEED_DATA.filter((j) => trackedIds.has(j.id));

  return (
    <div className="fixed inset-0 z-50 animate-fade-in" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm" />

      <aside
        className="absolute top-0 right-0 h-full w-full max-w-sm bg-white shadow-2xl flex flex-col animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
        style={{ animation: 'slideInRight 0.25s ease-out' }}
        id="tracked-drawer"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
            <h2 className="text-base font-semibold text-slate-900">Tracked Jobs</h2>
            <span className="ml-1 text-xs text-slate-400">({tracked.length})</span>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {tracked.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <svg className="w-10 h-10 text-slate-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              <p className="text-sm text-slate-400">No tracked jobs yet.</p>
              <p className="text-xs text-slate-300 mt-1">Click "Track" on any listing to save it here.</p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {tracked.map((job) => (
                <li key={job.id} className="px-5 py-4 flex items-start justify-between hover:bg-slate-50 transition-colors">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{job.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{job.company} · {job.location}</p>
                    <p className="text-2xs text-slate-400 mt-1">{job.postedAt}</p>
                  </div>
                  <button
                    onClick={() => onRemove(job.id)}
                    className="ml-3 p-1 text-slate-300 hover:text-maple rounded transition-colors flex-shrink-0"
                    title="Remove"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <style jsx>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
