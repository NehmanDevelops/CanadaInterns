import './globals.css';

export const metadata = {
  title: 'Canada Interns — Internship Discovery for Canadian Students',
  description:
    'Discover Canadian internships and tailor your resume with AI. Browse the latest listings, filter by location and field, and apply with confidence.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-700 font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
