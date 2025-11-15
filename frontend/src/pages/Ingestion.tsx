/**
 * Ingestion page - Unified interface for managing conversation log ingestion.
 *
 * Combines bulk upload, watch directory configuration, live activity monitoring,
 * and ingestion history into a single tabbed interface.
 */

import { useState } from 'react';
import { Upload, FolderSearch, Activity, History } from 'lucide-react';

type Tab = 'upload' | 'watch' | 'activity' | 'history';

export default function Ingestion() {
  const [activeTab, setActiveTab] = useState<Tab>('upload');

  const tabs = [
    { id: 'upload' as Tab, label: 'Bulk Upload', icon: Upload },
    { id: 'watch' as Tab, label: 'Watch Directories', icon: FolderSearch },
    { id: 'activity' as Tab, label: 'Live Activity', icon: Activity },
    { id: 'history' as Tab, label: 'History & Logs', icon: History },
  ];

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Ingestion Management</h1>
        <p className="text-muted-foreground">
          Upload conversation logs, configure watch directories, and monitor ingestion activity
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border mb-6">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm
                  transition-colors duration-200
                  ${
                    isActive
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon
                  className={`
                    -ml-0.5 mr-2 h-5 w-5
                    ${
                      isActive
                        ? 'text-primary'
                        : 'text-muted-foreground group-hover:text-foreground'
                    }
                  `}
                  aria-hidden="true"
                />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'upload' && <BulkUploadTab />}
        {activeTab === 'watch' && <WatchDirectoriesTab />}
        {activeTab === 'activity' && <LiveActivityTab />}
        {activeTab === 'history' && <HistoryLogsTab />}
      </div>
    </div>
  );
}

// Placeholder tab components - will be implemented in separate beads

function BulkUploadTab() {
  return (
    <div className="bg-card border border-border rounded-lg p-8">
      <h2 className="text-2xl font-semibold mb-4">Bulk Upload</h2>
      <p className="text-muted-foreground">
        Upload conversation log files (.jsonl) for batch processing.
      </p>
      <div className="mt-8 text-center text-muted-foreground">
        Coming soon - will migrate content from Upload.tsx
      </div>
    </div>
  );
}

function WatchDirectoriesTab() {
  return (
    <div className="bg-card border border-border rounded-lg p-8">
      <h2 className="text-2xl font-semibold mb-4">Watch Directories</h2>
      <p className="text-muted-foreground">
        Configure directories for automatic conversation log monitoring and ingestion.
      </p>
      <div className="mt-8 text-center text-muted-foreground">
        Coming soon - create, edit, delete, start/stop watch configurations
      </div>
    </div>
  );
}

function LiveActivityTab() {
  return (
    <div className="bg-card border border-border rounded-lg p-8">
      <h2 className="text-2xl font-semibold mb-4">Live Activity</h2>
      <p className="text-muted-foreground">
        Monitor active watch directories and recent ingestion jobs in real-time.
      </p>
      <div className="mt-8 text-center text-muted-foreground">
        Coming soon - real-time job stream with auto-refresh
      </div>
    </div>
  );
}

function HistoryLogsTab() {
  return (
    <div className="bg-card border border-border rounded-lg p-8">
      <h2 className="text-2xl font-semibold mb-4">History & Logs</h2>
      <p className="text-muted-foreground">
        View detailed history of all ingestion jobs with filtering and statistics.
      </p>
      <div className="mt-8 text-center text-muted-foreground">
        Coming soon - job history table with pagination and filters
      </div>
    </div>
  );
}
