export default function Hero() {
  return (
    <section className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <div className="max-w-2xl">
          {/* Dateline */}
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-2xs font-semibold uppercase tracking-wider text-maple bg-maple-50 rounded">
              <span className="w-1.5 h-1.5 rounded-full bg-maple" style={{ animation: 'pulse-dot 2s ease-in-out infinite' }} />
              Live
            </span>
            <span className="text-xs text-slate-400">Updated every 5 minutes</span>
          </div>

          {/* Headline */}
          <h1 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold text-slate-900 leading-tight tracking-tight mb-4">
            Canadian internships,<br />
            <span className="text-maple">tailored to&nbsp;you.</span>
          </h1>

          {/* Subhead */}
          <p className="text-base sm:text-lg text-slate-500 leading-relaxed max-w-lg mb-6">
            Browse real-time listings from across Canada. When you find the right one, our AI rewrites your resume bullets to match — no formatting changes, just better keyword alignment.
          </p>

          {/* CTA */}
          <div className="flex flex-wrap gap-3">
            <a
              href="#listings"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-maple text-white text-sm font-semibold rounded-md hover:bg-maple-dark transition-colors shadow-sm"
              id="hero-browse-btn"
            >
              Browse listings
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </a>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-100 text-slate-700 text-sm font-semibold rounded-md hover:bg-slate-200 transition-colors"
              id="hero-how-btn"
            >
              How it works
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
