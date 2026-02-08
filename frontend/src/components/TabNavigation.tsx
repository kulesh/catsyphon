/**
 * TabNavigation - Shared tab navigation component.
 *
 * Two visual variants matching existing page styles:
 * - observatory: Dark bg, cyan highlights, rounded container (ProjectDetail, ConversationDetail)
 * - underline: Border-bottom based (Ingestion)
 */

import type { ComponentType } from 'react';

export interface TabDefinition<T extends string> {
  id: T;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

interface TabNavigationProps<T extends string> {
  tabs: TabDefinition<T>[];
  activeTab: T;
  onTabChange: (tab: T) => void;
  variant?: 'observatory' | 'underline';
}

export function TabNavigation<T extends string>({
  tabs,
  activeTab,
  onTabChange,
  variant = 'observatory',
}: TabNavigationProps<T>) {
  if (variant === 'underline') {
    return (
      <div className="border-b border-border mb-6">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
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
    );
  }

  // Observatory variant (default)
  return (
    <div className="mb-8">
      <nav className="flex gap-2 bg-slate-900/30 p-1 rounded-lg border border-border/50" aria-label="Tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                flex-1 inline-flex items-center justify-center gap-2 py-3 px-4 rounded-md font-mono text-xs font-semibold uppercase tracking-wider
                transition-all duration-200
                ${
                  isActive
                    ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent/30'
                }
              `}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {tab.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
