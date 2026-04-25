'use client';

import { useState } from 'react';

export default function Header({
  trackedCount,
  onOpenTracked,
}: {
  trackedCount: number;
  onOpenTracked: () => void;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <a href="/" className="flex items-center gap-2 group" id="header-logo">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded bg-maple text-white font-display font-bold text-lg leading-none">
              C
            </span>
            <span className="text-slate-900 font-semibold text-base tracking-tight">
              Canada<span className="text-maple">&nbsp;Interns</span>
            </span>
          </a>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1 text-sm" id="header-nav">
            <a href="#listings" className="px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors">
              Listings
            </a>
            <a href="#how-it-works" className="px-3 py-1.5 rounded-md text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors">
              How It Works
            </a>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenTracked}
              className="relative inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
              id="tracked-jobs-btn"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Tracked
              {trackedCount > 0 && (
                <span className="inline-flex items-center justify-center w-5 h-5 text-2xs font-bold bg-maple text-white rounded-full">
                  {trackedCount}
                </span>
              )}
            </button>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-1.5 text-slate-500 hover:text-slate-800 rounded-md"
              id="mobile-menu-btn"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white animate-slide-down">
          <nav className="px-4 py-3 flex flex-col gap-1 text-sm">
            <a href="#listings" className="px-3 py-2 rounded-md text-slate-600 hover:bg-slate-100" onClick={() => setMobileOpen(false)}>
              Listings
            </a>
            <a href="#how-it-works" className="px-3 py-2 rounded-md text-slate-600 hover:bg-slate-100" onClick={() => setMobileOpen(false)}>
              How It Works
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}
