'use client';

import { useState, useCallback, useRef } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import InternshipBoard, { Internship } from './components/InternshipBoard';
import HowItWorks from './components/HowItWorks';
import Footer from './components/Footer';
import TrackedDrawer from './components/TrackedDrawer';

export default function Home() {
  const [trackedIds, setTrackedIds] = useState<Set<string>>(new Set());
  const [trackedJobs, setTrackedJobs] = useState<Internship[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const toggleTrack = useCallback((id: string, job?: Internship) => {
    setTrackedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        setTrackedJobs((pj) => pj.filter((j) => j.id !== id));
      } else {
        next.add(id);
        if (job) setTrackedJobs((pj) => [...pj, job]);
      }
      return next;
    });
  }, []);

  return (
    <>
      <Header trackedCount={trackedIds.size} onOpenTracked={() => setDrawerOpen(true)} />
      <Hero />
      <InternshipBoard trackedIds={trackedIds} onToggleTrack={toggleTrack} />
      <HowItWorks />
      <Footer />
      <TrackedDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        trackedJobs={trackedJobs}
        onRemove={(id) => toggleTrack(id)}
      />
    </>
  );
}
