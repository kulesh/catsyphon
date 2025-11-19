/**
 * Setup wizard for first-time onboarding.
 *
 * Guides users through creating an organization and workspace.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createOrganization,
  createWorkspace,
  generateSlug,
  type OrganizationCreate,
  type WorkspaceCreate,
  type Organization,
  type Workspace,
} from '@/lib/api-setup';

type Step = 'welcome' | 'organization' | 'workspace' | 'success';

export default function Setup() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('welcome');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Organization form state
  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [organization, setOrganization] = useState<Organization | null>(null);

  // Workspace form state
  const [workspaceName, setWorkspaceName] = useState('');
  const [workspaceSlug, setWorkspaceSlug] = useState('');
  const [workspace, setWorkspace] = useState<Workspace | null>(null);

  // Auto-generate slug when name changes
  useEffect(() => {
    if (step === 'organization' && orgName) {
      setOrgSlug(generateSlug(orgName));
    }
  }, [orgName, step]);

  useEffect(() => {
    if (step === 'workspace' && workspaceName) {
      setWorkspaceSlug(generateSlug(workspaceName));
    }
  }, [workspaceName, step]);

  const handleCreateOrganization = async () => {
    if (!orgName.trim()) {
      setError('Please enter an organization name');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data: OrganizationCreate = {
        name: orgName.trim(),
        slug: orgSlug.trim() || undefined,
      };

      const created = await createOrganization(data);
      setOrganization(created);
      setStep('workspace');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create organization');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkspace = async () => {
    if (!workspaceName.trim()) {
      setError('Please enter a workspace name');
      return;
    }

    if (!organization) {
      setError('No organization selected');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data: WorkspaceCreate = {
        organization_id: organization.id,
        name: workspaceName.trim(),
        slug: workspaceSlug.trim() || undefined,
      };

      const created = await createWorkspace(data);
      setWorkspace(created);
      setStep('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = () => {
    // Navigate to ingestion page so users can start ingesting data
    navigate('/ingestion');
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 grid-pattern relative overflow-hidden">
      {/* Scan line effect */}
      <div className="absolute inset-0 scan-line pointer-events-none" />

      <div className="max-w-2xl w-full relative z-10">
        {/* Welcome Step */}
        {step === 'welcome' && (
          <div className="observatory-card p-10 text-center animate-fade-in">
            {/* Mission badge */}
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-cyan-400/10 border-2 border-cyan-400/30 flex items-center justify-center glow-cyan">
              <span className="text-4xl">🐱</span>
            </div>

            <h1 className="text-5xl font-display tracking-wide text-foreground mb-4">
              OBSERVATORY INIT
            </h1>
            <p className="text-lg text-muted-foreground font-body mb-2">
              Mission Control Setup Protocol v1.0
            </p>
            <p className="text-sm font-mono text-muted-foreground/70 mb-10">
              Initializing workspace telemetry system...
            </p>

            <div className="observatory-card border-cyan-400/20 p-8 mb-10 text-left">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-2 h-2 bg-cyan-400 rounded-full pulse-dot" />
                <h3 className="text-lg font-heading font-semibold text-foreground">
                  Mission Parameters
                </h3>
              </div>
              <dl className="space-y-5">
                <div>
                  <dt className="font-mono text-sm font-semibold text-cyan-400 mb-2">
                    &gt; ORGANIZATION
                  </dt>
                  <dd className="text-sm text-muted-foreground leading-relaxed pl-4 border-l-2 border-cyan-400/30">
                    Your command center. All operations and workspaces are managed under your organization umbrella.
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-sm font-semibold text-emerald-400 mb-2">
                    &gt; WORKSPACE
                  </dt>
                  <dd className="text-sm text-muted-foreground leading-relaxed pl-4 border-l-2 border-emerald-400/30">
                    Isolated telemetry zones for organizing agent conversations by project, team, or environment.
                  </dd>
                </div>
              </dl>
            </div>

            <button
              onClick={() => setStep('organization')}
              className="group relative px-10 py-4 bg-gradient-to-r from-cyan-500 to-cyan-400 text-slate-950 font-mono font-bold rounded-lg overflow-hidden transition-all hover:glow-cyan"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-cyan-300 opacity-0 group-hover:opacity-100 transition-opacity" />
              <span className="relative flex items-center gap-2">
                INITIATE SETUP
                <span className="group-hover:translate-x-1 transition-transform">→</span>
              </span>
            </button>
          </div>
        )}

        {/* Organization Step */}
        {step === 'organization' && (
          <div className="observatory-card p-8 animate-fade-in">
            {/* Header with step indicator */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-cyan-400/20 border border-cyan-400/50 flex items-center justify-center">
                    <span className="text-sm font-mono font-bold text-cyan-400">1</span>
                  </div>
                  <h2 className="text-3xl font-display tracking-wide text-foreground">
                    ORGANIZATION
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-cyan-400 rounded-full" />
                  <div className="w-2 h-2 bg-muted rounded-full opacity-30" />
                  <span className="text-xs font-mono text-muted-foreground ml-2">STEP 1/2</span>
                </div>
              </div>
              <p className="text-muted-foreground font-mono text-sm pl-11">
                Configure your command center identity
              </p>
            </div>

            <div className="space-y-6">
              {/* Organization Name Field */}
              <div>
                <label
                  htmlFor="org-name"
                  className="block text-xs font-mono font-semibold text-cyan-400 mb-3 tracking-wider"
                >
                  &gt; ORGANIZATION_NAME *
                </label>
                <input
                  id="org-name"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="ACME Corporation"
                  className="w-full px-4 py-3 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-cyan-400/50 focus:border-cyan-400/50 transition-all font-body"
                />
                <p className="text-xs font-mono text-muted-foreground/70 mt-2 pl-4">
                  → Company, team, or personal identifier
                </p>
              </div>

              {/* URL Slug Field */}
              <div>
                <label
                  htmlFor="org-slug"
                  className="block text-xs font-mono font-semibold text-emerald-400 mb-3 tracking-wider"
                >
                  &gt; URL_SLUG
                  <span
                    className="ml-2 text-muted-foreground/50 cursor-help text-[10px]"
                    title="Auto-generated URL identifier. Customize if needed."
                  >
                    [AUTO]
                  </span>
                </label>
                <input
                  id="org-slug"
                  type="text"
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  placeholder="acme-corporation"
                  pattern="[a-z0-9-]+"
                  className="w-full px-4 py-3 bg-background border border-border rounded-lg text-emerald-400 placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400/50 transition-all font-mono text-sm"
                />
                <p className="text-xs font-mono text-muted-foreground/70 mt-2 pl-4">
                  → lowercase-hyphenated-format
                </p>
              </div>

              {/* Error Display */}
              {error && (
                <div className="observatory-card border-rose-400/50 bg-rose-500/10 p-4">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 bg-rose-400 rounded-full" />
                    <p className="text-sm font-mono text-rose-400">{error}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-between pt-6 border-t border-border/30">
                <button
                  onClick={() => setStep('welcome')}
                  className="group px-6 py-2 text-muted-foreground hover:text-foreground transition-colors font-mono text-sm"
                >
                  <span className="group-hover:-translate-x-1 inline-block transition-transform">←</span> BACK
                </button>
                <button
                  onClick={handleCreateOrganization}
                  disabled={loading || !orgName.trim()}
                  className="group relative px-8 py-3 bg-gradient-to-r from-cyan-500 to-cyan-400 text-slate-950 font-mono font-bold rounded-lg overflow-hidden transition-all hover:glow-cyan disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:glow-none"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-cyan-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                  <span className="relative flex items-center gap-2">
                    {loading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin" />
                        CREATING...
                      </>
                    ) : (
                      <>
                        CONTINUE
                        <span className="group-hover:translate-x-1 transition-transform">→</span>
                      </>
                    )}
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Workspace Step */}
        {step === 'workspace' && organization && (
          <div className="observatory-card p-8 animate-fade-in">
            {/* Header with step indicator */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-emerald-400/20 border border-emerald-400/50 flex items-center justify-center">
                    <span className="text-sm font-mono font-bold text-emerald-400">2</span>
                  </div>
                  <h2 className="text-3xl font-display tracking-wide text-foreground">
                    WORKSPACE
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-cyan-400 rounded-full opacity-50" />
                  <div className="w-2 h-2 bg-emerald-400 rounded-full" />
                  <span className="text-xs font-mono text-muted-foreground ml-2">STEP 2/2</span>
                </div>
              </div>
              <div className="pl-11">
                <p className="text-muted-foreground font-mono text-sm mb-2">
                  Configure telemetry zone
                </p>
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-muted-foreground/50">PARENT:</span>
                  <span className="font-mono text-cyan-400">{organization.name}</span>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              {/* Workspace Name Field */}
              <div>
                <label
                  htmlFor="workspace-name"
                  className="block text-xs font-mono font-semibold text-emerald-400 mb-3 tracking-wider"
                >
                  &gt; WORKSPACE_NAME *
                </label>
                <input
                  id="workspace-name"
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  placeholder="Engineering"
                  className="w-full px-4 py-3 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400/50 transition-all font-body"
                />
                <p className="text-xs font-mono text-muted-foreground/70 mt-2 pl-4">
                  → Team, project, or environment identifier
                </p>
              </div>

              {/* URL Slug Field */}
              <div>
                <label
                  htmlFor="workspace-slug"
                  className="block text-xs font-mono font-semibold text-amber-400 mb-3 tracking-wider"
                >
                  &gt; URL_SLUG
                  <span
                    className="ml-2 text-muted-foreground/50 cursor-help text-[10px]"
                    title="Auto-generated URL identifier. Customize if needed."
                  >
                    [AUTO]
                  </span>
                </label>
                <input
                  id="workspace-slug"
                  type="text"
                  value={workspaceSlug}
                  onChange={(e) => setWorkspaceSlug(e.target.value)}
                  placeholder="engineering"
                  pattern="[a-z0-9-]+"
                  className="w-full px-4 py-3 bg-background border border-border rounded-lg text-amber-400 placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400/50 transition-all font-mono text-sm"
                />
                <p className="text-xs font-mono text-muted-foreground/70 mt-2 pl-4">
                  → lowercase-hyphenated-format
                </p>
              </div>

              {/* Error Display */}
              {error && (
                <div className="observatory-card border-rose-400/50 bg-rose-500/10 p-4">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 bg-rose-400 rounded-full" />
                    <p className="text-sm font-mono text-rose-400">{error}</p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex justify-between pt-6 border-t border-border/30">
                <button
                  onClick={() => {
                    setStep('organization');
                    setError(null);
                  }}
                  className="group px-6 py-2 text-muted-foreground hover:text-foreground transition-colors font-mono text-sm"
                >
                  <span className="group-hover:-translate-x-1 inline-block transition-transform">←</span> BACK
                </button>
                <button
                  onClick={handleCreateWorkspace}
                  disabled={loading || !workspaceName.trim()}
                  className="group relative px-8 py-3 bg-gradient-to-r from-emerald-500 to-emerald-400 text-slate-950 font-mono font-bold rounded-lg overflow-hidden transition-all hover:glow-emerald disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:glow-none"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-emerald-400 to-emerald-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                  <span className="relative flex items-center gap-2">
                    {loading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin" />
                        CREATING...
                      </>
                    ) : (
                      <>
                        FINALIZE SETUP
                        <span className="group-hover:translate-x-1 transition-transform">→</span>
                      </>
                    )}
                  </span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Step */}
        {step === 'success' && organization && workspace && (
          <div className="observatory-card p-10 text-center animate-fade-in">
            <div className="mb-8">
              {/* Success icon with animation */}
              <div className="relative w-24 h-24 mx-auto mb-6">
                <div className="absolute inset-0 bg-emerald-400/20 rounded-full animate-ping" />
                <div className="relative w-24 h-24 bg-emerald-400/10 border-2 border-emerald-400/50 rounded-full flex items-center justify-center glow-emerald">
                  <svg
                    className="w-12 h-12 text-emerald-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              </div>

              <h2 className="text-4xl font-display tracking-wide text-foreground mb-3">
                INITIALIZATION COMPLETE
              </h2>
              <p className="text-muted-foreground font-mono text-sm mb-2">
                Observatory systems online
              </p>
              <div className="flex items-center justify-center gap-2">
                <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full pulse-dot" />
                <p className="text-xs font-mono text-emerald-400">
                  ALL SYSTEMS OPERATIONAL
                </p>
              </div>
            </div>

            {/* Configuration summary */}
            <div className="observatory-card border-emerald-400/20 p-6 mb-8 text-left max-w-md mx-auto">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xs font-mono text-muted-foreground">CONFIGURATION:</span>
              </div>
              <dl className="space-y-3">
                <div className="flex items-start gap-3">
                  <dt className="text-xs font-mono text-cyan-400 min-w-[120px] pt-1">
                    &gt; ORGANIZATION:
                  </dt>
                  <dd className="text-sm font-body text-foreground font-semibold">
                    {organization.name}
                  </dd>
                </div>
                <div className="flex items-start gap-3">
                  <dt className="text-xs font-mono text-emerald-400 min-w-[120px] pt-1">
                    &gt; WORKSPACE:
                  </dt>
                  <dd className="text-sm font-body text-foreground font-semibold">
                    {workspace.name}
                  </dd>
                </div>
                <div className="flex items-start gap-3">
                  <dt className="text-xs font-mono text-amber-400 min-w-[120px] pt-1">
                    &gt; STATUS:
                  </dt>
                  <dd className="text-sm font-mono text-emerald-400">
                    ACTIVE
                  </dd>
                </div>
              </dl>
            </div>

            <button
              onClick={handleComplete}
              className="group relative px-10 py-4 bg-gradient-to-r from-emerald-500 to-emerald-400 text-slate-950 font-mono font-bold rounded-lg overflow-hidden transition-all hover:glow-emerald"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-emerald-400 to-emerald-300 opacity-0 group-hover:opacity-100 transition-opacity" />
              <span className="relative flex items-center gap-2">
                ENTER MISSION CONTROL
                <span className="group-hover:translate-x-1 transition-transform">→</span>
              </span>
            </button>

            <p className="text-xs font-mono text-muted-foreground/50 mt-6">
              Ready to ingest and analyze agent conversations
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
