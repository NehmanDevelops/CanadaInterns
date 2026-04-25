'use client';

const LOCATIONS = [
  'All Locations',
  'Toronto, ON',
  'Vancouver, BC',
  'Montreal, QC',
  'Ottawa, ON',
  'Calgary, AB',
  'Winnipeg, MB',
  'Victoria, BC',
];

const FIELDS = [
  'All Fields',
  'Software & Engineering',
  'Marketing & Media',
  'Data & Analytics',
  'Finance',
  'Design',
  'Policy & Government',
  'Science & Environment',
  'Product Management',
  'Journalism',
];

const DATE_OPTIONS = [
  { label: 'Any time', value: '' },
  { label: 'Past 24 hours', value: '1' },
  { label: 'Past 3 days', value: '3' },
  { label: 'Past week', value: '7' },
];

interface FilterBarProps {
  location: string;
  field: string;
  datePosted: string;
  onLocationChange: (v: string) => void;
  onFieldChange: (v: string) => void;
  onDateChange: (v: string) => void;
  resultCount: number;
}

export default function FilterBar({
  location,
  field,
  datePosted,
  onLocationChange,
  onFieldChange,
  onDateChange,
  resultCount,
}: FilterBarProps) {
  const selectClasses =
    'appearance-none bg-white border border-slate-200 rounded-md px-3 py-2 pr-8 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-maple/30 focus:border-maple transition-colors cursor-pointer';

  return (
    <div className="bg-white border-b border-slate-200 sticky top-14 z-40" id="filter-bar">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 flex-1">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 mr-1">
              Filter
            </label>

            <div className="relative">
              <select
                value={location}
                onChange={(e) => onLocationChange(e.target.value)}
                className={selectClasses}
                id="filter-location"
              >
                {LOCATIONS.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
              <ChevronIcon />
            </div>

            <div className="relative">
              <select
                value={field}
                onChange={(e) => onFieldChange(e.target.value)}
                className={selectClasses}
                id="filter-field"
              >
                {FIELDS.map((f) => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
              <ChevronIcon />
            </div>

            <div className="relative">
              <select
                value={datePosted}
                onChange={(e) => onDateChange(e.target.value)}
                className={selectClasses}
                id="filter-date"
              >
                {DATE_OPTIONS.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
              <ChevronIcon />
            </div>
          </div>

          {/* Result count */}
          <span className="text-xs text-slate-400 whitespace-nowrap">
            {resultCount} listing{resultCount !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </div>
  );
}

function ChevronIcon() {
  return (
    <svg
      className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}
