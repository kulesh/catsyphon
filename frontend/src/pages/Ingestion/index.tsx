/**
 * Ingestion page - Unified interface for managing conversation log ingestion.
 *
 * Combines bulk upload, watch directory configuration, live activity monitoring,
 * and ingestion history into a single tabbed interface.
 */

import { useState } from 'react';
import {
  Upload,
  FolderSearch,
  Activity,
  History,
} from 'lucide-react';
import { TabNavigation, type TabDefinition } from '@/components';
import BulkUploadTab from './BulkUploadTab';
import WatchDirectoriesTab from './WatchDirectoriesTab';
import LiveActivityTab from './LiveActivityTab';
import HistoryLogsTab from './HistoryLogsTab';

type Tab = 'upload' | 'watch' | 'activity' | 'history';

export default function Ingestion() {
  const [activeTab, setActiveTab] = useState<Tab>('upload');

  const tabs: TabDefinition<Tab>[] = [
    { id: 'upload', label: 'Bulk Upload', icon: Upload },
    { id: 'watch', label: 'Watch Directories', icon: FolderSearch },
    { id: 'activity', label: 'Live Activity', icon: Activity },
    { id: 'history', label: 'History & Logs', icon: History },
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
      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} variant="underline" />

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
