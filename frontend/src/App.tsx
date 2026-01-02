/**
 * Root application component with routing.
 */

import { useEffect, useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { checkSetupStatus } from '@/lib/api-setup';

export default function App() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function checkOnboarding() {
      try {
        const status = await checkSetupStatus();
        if (status.needs_onboarding) {
          navigate('/setup');
        }
      } catch (error) {
        console.error('Failed to check setup status:', error);
      } finally {
        setChecking(false);
      }
    }

    checkOnboarding();
  }, [navigate]);

  // Show loading state while checking
  if (checking) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center grid-pattern">
        <div className="text-center">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-2 border-transparent border-t-cyan-400 border-r-cyan-400 mx-auto mb-6 glow-cyan"></div>
            <div className="absolute inset-0 animate-ping rounded-full h-16 w-16 border border-cyan-400/20 mx-auto"></div>
          </div>
          <p className="text-sm font-mono text-muted-foreground tracking-wider">INITIALIZING OBSERVATORY...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Observatory Navigation */}
      <nav className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur-sm">
        <div className="absolute inset-0 grid-pattern opacity-30" />
        <div className="container mx-auto px-6 py-4 relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-10">
              {/* Logo */}
              <Link
                to="/"
                className="group flex items-center gap-3 hover:opacity-80 transition-opacity"
              >
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-600 flex items-center justify-center glow-cyan">
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    className="text-slate-950"
                  >
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                  </svg>
                </div>
                <span className="text-xl font-display tracking-wide text-foreground">
                  CatSyphon
                </span>
                <div className="w-2 h-2 rounded-full bg-cyan-400 pulse-dot opacity-60" />
              </Link>

              {/* Nav Links */}
              <div className="flex gap-1">
                <Link
                  to="/conversations"
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-lg transition-all"
                >
                  Conversations
                </Link>
                <Link
                  to="/projects"
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-lg transition-all"
                >
                  Projects
                </Link>
                <Link
                  to="/ingestion"
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-lg transition-all"
                >
                  Ingestion
                </Link>
                <Link
                  to="/benchmarks"
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-lg transition-all"
                >
                  Benchmarks
                </Link>
              </div>
            </div>

            {/* Status Indicator */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent/30 border border-border">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
              <span className="text-xs font-mono text-muted-foreground">SYSTEM ONLINE</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Page content */}
      <main>
        <Outlet />
      </main>
    </div>
  );
}
