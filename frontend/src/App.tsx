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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="text-xl font-bold hover:text-primary">
                CatSyphon
              </Link>
              <div className="flex gap-4">
                <Link
                  to="/conversations"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Conversations
                </Link>
                <Link
                  to="/projects"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Projects
                </Link>
                <Link
                  to="/ingestion"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Ingestion
                </Link>
              </div>
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
