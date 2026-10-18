import './globals.css';
import type { Metadata } from 'next';
import { DemoProvider } from '@/lib/demo-context';
import { SiteNav } from '@/components/shared/SiteNav';
export const metadata: Metadata = {
 icons: { icon: "/probe-icon.png" },
 title: 'Probe | Find Clinical Trial Risks Before Patients Enroll',
 description: 'Probe checks whether fake site records can pass monitoring and whether staff records reveal treatment assignments. Simulation only.'
};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><head><link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous"/><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter+Tight:wght@400;500;600;700;800&display=swap" rel="stylesheet"/></head><body><DemoProvider><SiteNav/>{children}</DemoProvider></body></html>}
