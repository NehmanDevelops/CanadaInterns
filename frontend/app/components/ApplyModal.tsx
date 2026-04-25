'use client';

import { useState } from 'react';
import { Internship } from './InternshipBoard';

interface ApplyModalProps {
  job: Internship;
  onClose: () => void;
}

export default function ApplyModal({ job, onClose }: ApplyModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState<'idle' | 'processing' | 'done'>('idle');

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith('.pdf') || dropped.name.endsWith('.docx'))) {
      setFile(dropped);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  const handleTailor = () => {
    if (!file) return;
    setStatus('processing');
    // Simulate AI processing
    setTimeout(() => setStatus('done'), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-start justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Apply with AI-Tailored Resume</h3>
            <p className="text-sm text-slate-500 mt-0.5">{job.title} at {job.company}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded transition-colors"
            id="apply-modal-close"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {status === 'idle' && (
            <>
              {/* Drop zone */}
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragOver
                    ? 'border-maple bg-maple-50'
                    : file
                    ? 'border-teal bg-teal-light'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                id="resume-dropzone"
              >
                {file ? (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-8 h-8 text-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm font-medium text-slate-700">{file.name}</p>
                    <button onClick={() => setFile(null)} className="text-xs text-slate-400 hover:text-maple">Remove</button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-sm text-slate-500">
                      Drag &amp; drop your resume, or{' '}
                      <label className="text-maple font-medium cursor-pointer hover:underline">
                        browse
                        <input type="file" accept=".pdf,.docx" className="hidden" onChange={handleFileChange} id="resume-file-input" />
                      </label>
                    </p>
                    <p className="text-xs text-slate-400">PDF or DOCX, max 5 MB</p>
                  </div>
                )}
              </div>

              {/* Job description preview */}
              <div className="mt-4 p-3 bg-slate-50 rounded-md border border-slate-200">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Job description</p>
                <p className="text-sm text-slate-600 line-clamp-3">{job.description}</p>
              </div>

              {/* Info note */}
              <div className="mt-4 flex items-start gap-2 text-xs text-slate-500">
                <svg className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  Our AI only rewrites bullet point descriptions to improve ATS keyword alignment. Your resume's formatting, structure, layout, and other content remain unchanged.
                </span>
              </div>
            </>
          )}

          {status === 'processing' && (
            <div className="py-12 flex flex-col items-center gap-4 animate-fade-in">
              {/* Spinner */}
              <div className="w-10 h-10 border-3 border-slate-200 border-t-maple rounded-full animate-spin" style={{ borderWidth: '3px' }} />
              <div className="text-center">
                <p className="text-sm font-medium text-slate-700">Tailoring your resume…</p>
                <p className="text-xs text-slate-400 mt-1">Matching keywords for {job.title}</p>
              </div>
            </div>
          )}

          {status === 'done' && (
            <div className="py-8 flex flex-col items-center gap-4 animate-fade-in">
              <div className="w-12 h-12 rounded-full bg-teal-light flex items-center justify-center">
                <svg className="w-6 h-6 text-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-900">Resume tailored successfully</p>
                <p className="text-xs text-slate-500 mt-1">Estimated ATS match: <span className="font-semibold text-teal">86%</span> (was 52%)</p>
              </div>

              {/* Mock diff */}
              <div className="w-full mt-2 p-3 bg-slate-50 rounded-md border border-slate-200 text-xs font-mono overflow-x-auto">
                <p className="text-slate-400 mb-2">// Changes preview</p>
                <p className="text-red-500 line-through">- Built web applications using modern frameworks</p>
                <p className="text-teal mb-2">+ Developed scalable web applications using React and Node.js, improving load times by 40%</p>
                <p className="text-red-500 line-through">- Worked on data analysis projects</p>
                <p className="text-teal">+ Conducted quantitative data analysis using Python and SQL, delivering actionable insights to stakeholders</p>
              </div>

              <button
                className="mt-2 inline-flex items-center gap-2 px-5 py-2.5 bg-maple text-white text-sm font-semibold rounded-md hover:bg-maple-dark transition-colors shadow-sm"
                id="download-resume-btn"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download tailored resume
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        {status === 'idle' && (
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleTailor}
              disabled={!file}
              className="px-5 py-2 text-sm font-semibold text-white bg-maple rounded-md hover:bg-maple-dark disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
              id="tailor-resume-btn"
            >
              Tailor &amp; Apply
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
