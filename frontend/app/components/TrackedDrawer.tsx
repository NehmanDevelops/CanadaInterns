'use client';

import { Internship } from './InternshipBoard';

interface TrackedDrawerProps {
  open: boolean;
  onClose: () => void;
  trackedJobs: Internship[];
  onRemove: (id: string) => void;
}

export default function TrackedDrawer({ open, onClose, trackedJobs, onRemove }: TrackedDrawerProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 animate-fade-in" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm" />

      <aside
        className="absolute top-0 right-0 h-full w-full max-w-sm bg-white shadow-2xl flex flex-col"
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
            <span className="ml-1 text-xs text-slate-400">({trackedJobs.length})</span>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded transition-colors">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {trackedJobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <svg className="w-10 h-10 text-slate-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              <p className="text-sm text-slate-400">No tracked jobs yet.</p>
              <p className="text-xs text-slate-300 mt-1">Click &quot;Track&quot; on any listing to save it here.</p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {trackedJobs.map((job) => (
                <li key={job.id} className="px-5 py-4 flex items-start justify-between hover:bg-slate-50 transition-colors">
                  <a href={job.url} target="_blank" rel="noopener noreferrer" className="min-w-0 flex-1 group">
                    <p className="text-sm font-medium text-slate-900 truncate group-hover:text-maple group-hover:underline">{job.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{job.company} · {job.location}</p>
                  </a>
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
