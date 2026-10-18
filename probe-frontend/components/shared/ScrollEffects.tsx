'use client';

import { useEffect, useRef } from 'react';

/** Progressive enhancement. Scrolling reveals information without concealing it when JS is disabled. */
export function ScrollEffects() {
  const bar = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const root = document.querySelector('.probe-home-v5');
    if (!root) return;

    const elements = Array.from(root.querySelectorAll<HTMLElement>('[data-scroll]'));
    if (!reduceMotion && 'IntersectionObserver' in window) {
      root.classList.add('motion-ready');
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-revealed');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -36px 0px' });
      elements.forEach((element, index) => {
        if (element.dataset.stagger) element.style.setProperty('--reveal-delay', `${Math.min(420, Number(element.dataset.stagger) * 95)}ms`);
        observer.observe(element);
      });
      const onScroll = () => {
        if (bar.current) {
          const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
          bar.current.style.transform = `scaleX(${Math.max(0, Math.min(1, window.scrollY / max))})`;
        }
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll);
      onScroll();
      return () => { observer.disconnect(); root.classList.remove('motion-ready'); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); };
    }
    elements.forEach(element => element.classList.add('is-revealed'));
    return undefined;
  }, []);

  return <div className="probe-scroll-progress" ref={bar} aria-hidden="true" />;
}
