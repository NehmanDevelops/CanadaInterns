'use client';

import { useState, useCallback } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import InternshipBoard from './components/InternshipBoard';
import HowItWorks from './components/HowItWorks';
import Footer from './components/Footer';
import TrackedDrawer from './components/TrackedDrawer';

export default function Home() {
  const [trackedIds, setTrackedIds] = useState<Set<number>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);

  const toggleTrack = useCallback((id: number) => {
    setTrackedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
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
        trackedIds={trackedIds}
        allJobs={[]}
        onRemove={toggleTrack}
      />
    </>
  );
}
