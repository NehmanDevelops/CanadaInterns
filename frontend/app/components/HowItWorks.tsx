export default function HowItWorks() {
  const steps = [
    {
      number: '01',
      title: 'Browse listings',
      description: 'Real-time internship postings from across Canada, refreshed every few minutes.',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      ),
    },
    {
      number: '02',
      title: 'Upload your resume',
      description: 'Drop in your PDF or DOCX. We extract the content without touching your formatting.',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      number: '03',
      title: 'AI rewrites your bullets',
      description: 'GPT-4o rewrites only the bullet descriptions to align with the job — nothing else changes.',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      ),
    },
    {
      number: '04',
      title: 'Review & download',
      description: 'See exactly what changed in a diff view with your estimated ATS score before and after.',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      ),
    },
  ];

  return (
    <section className="bg-white border-t border-slate-200" id="how-it-works">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Section heading */}
        <div className="text-center mb-12">
          <h2 className="font-display text-2xl sm:text-3xl font-bold text-slate-900 mb-3">
            How it works
          </h2>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            From browsing to a tailored resume in under two minutes. No sign-up required to explore.
          </p>
        </div>

        {/* Steps grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((step) => (
            <div key={step.number} className="relative group">
              {/* Step card */}
              <div className="p-5 rounded-lg border border-slate-200 bg-slate-50 group-hover:bg-white group-hover:border-slate-300 group-hover:shadow-md transition-all duration-200 h-full">
                {/* Number + Icon */}
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-2xs font-bold text-maple uppercase tracking-widest">{step.number}</span>
                  <div className="w-8 h-8 rounded-md bg-maple-50 text-maple flex items-center justify-center">
                    {step.icon}
                  </div>
                </div>

                <h3 className="text-sm font-semibold text-slate-900 mb-1.5">{step.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
