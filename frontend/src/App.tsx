/**
 * Root application component with routing.
 */

import { Link, Outlet } from 'react-router-dom';

export default function App() {
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
