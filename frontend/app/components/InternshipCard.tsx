'use client';

import React from 'react';

interface CardJob {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  ats_platform: string;
  postedAt: string;
}

interface InternshipCardProps {
  job: CardJob;
  isTracked: boolean;
  onTrack: () => void;
  onApply: () => void;
  index: number;
}

export default function InternshipCard({ job, isTracked, onTrack, onApply, index }: InternshipCardProps) {
  const { title, company, location, url, ats_platform, postedAt } = job;

  const platformLabel = ats_platform === 'greenhouse' ? 'Greenhouse' : ats_platform === 'lever' ? 'Lever' : ats_platform;

  return (
    <article
      className="group bg-white border border-slate-200 rounded-lg hover:border-slate-300 hover:shadow-md transition-all duration-200"
      style={{ animationDelay: `${index * 0.03}s` }}
      id={`listing-${index}`}
    >
      <div className="p-5">
        {/* Top row: platform tag + timestamp */}
        <div className="flex items-start justify-between mb-3">
          <span className="inline-block px-2 py-0.5 text-2xs font-semibold uppercase tracking-wider text-teal bg-teal-light rounded">
            {platformLabel}
          </span>
          <time className="text-2xs text-slate-400 whitespace-nowrap ml-3">{postedAt}</time>
        </div>

        {/* Title — links to the actual job posting */}
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-base font-semibold text-slate-900 leading-snug mb-1 group-hover:text-maple transition-colors hover:underline"
        >
          {title}
          <svg className="inline-block w-3 h-3 ml-1 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>

        {/* Company + Location */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
          <span className="font-medium text-slate-600">{company}</span>
          <span className="text-slate-300">·</span>
          <span className="inline-flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            {location}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-3 border-t border-slate-100">
          <button
            onClick={onApply}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-maple text-white text-sm font-semibold rounded-md hover:bg-maple-dark active:scale-[0.98] transition-all shadow-sm"
            id={`apply-btn-${index}`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
            Apply
          </button>

          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md transition-all"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View
          </a>

          <button
            onClick={onTrack}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all active:scale-[0.98] ${
              isTracked
                ? 'bg-slate-900 text-white hover:bg-slate-800'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
            id={`track-btn-${index}`}
          >
            <svg className="w-3.5 h-3.5" fill={isTracked ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
            {isTracked ? 'Tracked' : 'Track'}
          </button>
        </div>
      </div>
    </article>
  );
}
