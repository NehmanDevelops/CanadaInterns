'use client';

import { useState, useRef } from 'react';
import { Internship } from './InternshipBoard';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

interface Change {
  original: string;
  replacement: string;
  reason: string;
}

interface AnalysisResult {
  changes: Change[];
  ats_before: number;
  ats_after: number;
  keywords_matched: string[];
  keywords_missing: string[];
}

interface ApplyModalProps {
  job: Internship;
  onClose: () => void;
}

export default function ApplyModal({ job, onClose }: ApplyModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState<'idle' | 'processing' | 'done' | 'error'>('idle');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [downloading, setDownloading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.name.endsWith('.pdf')) {
      setFile(dropped);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  // Build a job description string from the job object
  const jobDescription = `${job.title} at ${job.company}\nLocation: ${job.location}\nApply: ${job.url}`;

  const handleTailor = async () => {
    if (!file) return;
    setStatus('processing');
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append('resume', file);
      formData.append('job_description', jobDescription);

      const res = await fetch(`${API_BASE}/api/resume/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data: AnalysisResult = await res.json();

      if ((data as any).error) {
        throw new Error((data as any).error);
      }

      setResult(data);
      setStatus('done');
    } catch (err: any) {
      setErrorMsg(err.message || 'Analysis failed');
      setStatus('error');
    }
  };

  const handleDownload = async () => {
    if (!file || !result) return;
    setDownloading(true);

    try {
      const formData = new FormData();
      formData.append('resume', file);
      formData.append('changes', JSON.stringify(result.changes.map(c => ({
        original: c.original,
        replacement: c.replacement,
      }))));

      const res = await fetch(`${API_BASE}/api/resume/download`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Download failed');

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tailored_resume_${job.company.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in" onClick={onClose}>
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" />

      <div
        className="relative bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white z-10 px-6 py-4 border-b border-slate-200 flex items-start justify-between rounded-t-xl">
          <div>
            <h3 className="text-base font-semibold text-slate-900">AI Resume Tailoring</h3>
            <p className="text-sm text-slate-500 mt-0.5">{job.title} at {job.company}</p>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded transition-colors" id="apply-modal-close">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {status === 'idle' && (
            <>
              {/* Direct link */}
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 mb-4 bg-red-50 border border-red-100 rounded-lg hover:bg-red-100 transition-colors group"
                id="apply-external-link"
              >
                <div className="w-9 h-9 rounded-md bg-maple flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-maple group-hover:underline">Apply directly on {job.company}</p>
                  <p className="text-xs text-slate-500 truncate">{job.url}</p>
                </div>
                <svg className="w-4 h-4 text-slate-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </a>

              {/* Divider */}
              <div className="flex items-center gap-3 mb-4">
                <hr className="flex-1 border-slate-200" />
                <span className="text-xs text-slate-400 uppercase tracking-wider">or tailor your resume first</span>
                <hr className="flex-1 border-slate-200" />
              </div>

              {/* Drop zone */}
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
                  dragOver ? 'border-maple bg-red-50' : file ? 'border-teal bg-teal-light' : 'border-slate-200 hover:border-slate-300'
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                id="resume-dropzone"
              >
                {file ? (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-8 h-8 text-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm font-medium text-slate-700">{file.name}</p>
                    <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-xs text-slate-400 hover:text-maple">Remove</button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="w-8 h-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-sm text-slate-500">
                      Drop your resume PDF here, or <span className="text-maple font-medium">browse</span>
                    </p>
                    <p className="text-xs text-slate-400">PDF only, max 5 MB</p>
                    <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileChange} id="resume-file-input" />
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="mt-4 flex items-start gap-2 text-xs text-slate-500">
                <svg className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>
                  AI rewrites 3–6 bullet points to match ATS keywords for <strong>{job.title}</strong>. Your formatting, layout, and structure stay untouched.
                </span>
              </div>
            </>
          )}

          {status === 'processing' && (
            <div className="py-12 flex flex-col items-center gap-4 animate-fade-in">
              <div className="w-10 h-10 border-[3px] border-slate-200 border-t-maple rounded-full animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-slate-700">Analyzing your resume with AI…</p>
                <p className="text-xs text-slate-400 mt-1">Matching keywords for {job.title}</p>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="py-8 flex flex-col items-center gap-4 animate-fade-in">
              <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
                <svg className="w-6 h-6 text-maple" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-900">Analysis failed</p>
                <p className="text-xs text-slate-500 mt-1">{errorMsg}</p>
              </div>
              <button
                onClick={() => { setStatus('idle'); setErrorMsg(''); }}
                className="text-sm text-maple hover:underline"
              >
                Try again
              </button>
            </div>
          )}

          {status === 'done' && result && (
            <div className="animate-fade-in space-y-5">
              {/* ATS Score */}
              <div className="flex items-center justify-center gap-6 py-4">
                <div className="text-center">
                  <p className="text-3xl font-bold text-slate-300">{result.ats_before}%</p>
                  <p className="text-xs text-slate-400 mt-1">Before</p>
                </div>
                <svg className="w-6 h-6 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
                <div className="text-center">
                  <p className="text-3xl font-bold text-teal">{result.ats_after}%</p>
                  <p className="text-xs text-slate-400 mt-1">After</p>
                </div>
              </div>

              {/* Note about format */}
              <div className="flex items-start gap-2 p-3 bg-teal-light rounded-lg text-xs text-slate-600">
                <svg className="w-4 h-4 text-teal flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Here&apos;s the ATS-adjusted resume for this job, without changing your format.</span>
              </div>

              {/* Changes */}
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Changes ({result.changes.length})</p>
                {result.changes.map((change, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs font-mono space-y-1.5">
                    <p className="text-red-500 line-through leading-relaxed">− {change.original}</p>
                    <p className="text-teal leading-relaxed">+ {change.replacement}</p>
                    <p className="text-slate-400 font-sans italic mt-1">{change.reason}</p>
                  </div>
                ))}
              </div>

              {/* Keywords */}
              {result.keywords_matched.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Keywords Matched</p>
                  <div className="flex flex-wrap gap-1.5">
                    {result.keywords_matched.map((kw, i) => (
                      <span key={i} className="px-2 py-0.5 text-2xs bg-teal-light text-teal rounded font-medium">{kw}</span>
                    ))}
                  </div>
                </div>
              )}
              {result.keywords_missing.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Still Missing</p>
                  <div className="flex flex-wrap gap-1.5">
                    {result.keywords_missing.map((kw, i) => (
                      <span key={i} className="px-2 py-0.5 text-2xs bg-red-50 text-red-400 rounded font-medium">{kw}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleDownload}
                  disabled={downloading}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-maple text-white text-sm font-semibold rounded-md hover:bg-maple-dark transition-colors shadow-sm disabled:opacity-60"
                  id="download-resume-btn"
                >
                  {downloading ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  )}
                  Download PDF
                </button>
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-100 text-slate-700 text-sm font-semibold rounded-md hover:bg-slate-200 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  Go apply
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Footer — idle only */}
        {status === 'idle' && (
          <div className="sticky bottom-0 bg-white z-10 px-6 py-4 border-t border-slate-200 flex items-center justify-end gap-3 rounded-b-xl">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition-colors">
              Cancel
            </button>
            <button
              onClick={handleTailor}
              disabled={!file}
              className="px-5 py-2 text-sm font-semibold text-white bg-maple rounded-md hover:bg-maple-dark disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm"
              id="tailor-resume-btn"
            >
              Tailor with AI
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
