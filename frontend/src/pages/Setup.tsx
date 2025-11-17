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
    // Navigate to dashboard
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {/* Welcome Step */}
        {step === 'welcome' && (
          <div className="bg-white rounded-lg shadow-xl p-8 text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Welcome to CatSyphon! 🐱
            </h1>
            <p className="text-lg text-gray-600 mb-2">
              Let's get you set up to start analyzing coding agent conversations.
            </p>
            <p className="text-sm text-gray-500 mb-8">
              We'll create an organization and workspace to organize your conversations.
            </p>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8 text-left">
              <h3 className="text-lg font-semibold text-blue-900 mb-3">
                What you'll create:
              </h3>
              <dl className="space-y-3">
                <div>
                  <dt className="font-medium text-blue-900">Organization</dt>
                  <dd className="text-sm text-blue-700 mt-1">
                    Your company, team, or personal account. All workspaces belong to an organization.
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-blue-900">Workspace</dt>
                  <dd className="text-sm text-blue-700 mt-1">
                    Helps organize conversations by project, team, or environment (e.g., production vs staging).
                  </dd>
                </div>
              </dl>
            </div>

            <button
              onClick={() => setStep('organization')}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 py-3 rounded-lg transition-colors"
            >
              Get Started
            </button>
          </div>
        )}

        {/* Organization Step */}
        {step === 'organization' && (
          <div className="bg-white rounded-lg shadow-xl p-8">
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-2xl font-bold text-gray-900">Create Organization</h2>
                <span className="text-sm text-gray-500">Step 1 of 2</span>
              </div>
              <p className="text-gray-600">
                Set up your organization to get started.
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <label
                  htmlFor="org-name"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Organization Name *
                </label>
                <input
                  id="org-name"
                  type="text"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g., ACME Corporation, My Company"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Your organization name (can be your company or personal name)
                </p>
              </div>

              <div>
                <label
                  htmlFor="org-slug"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  URL Slug
                  <span
                    className="ml-2 text-gray-400 cursor-help"
                    title="A URL-friendly identifier used in web addresses. Auto-generated from your name but you can customize it."
                  >
                    ⓘ
                  </span>
                </label>
                <input
                  id="org-slug"
                  type="text"
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  placeholder="e.g., acme-corporation"
                  pattern="[a-z0-9-]+"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Used in URLs - lowercase, no spaces (auto-generated)
                </p>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              <div className="flex justify-between pt-4">
                <button
                  onClick={() => setStep('welcome')}
                  className="px-6 py-2 text-gray-700 hover:text-gray-900 transition-colors"
                >
                  ← Back
                </button>
                <button
                  onClick={handleCreateOrganization}
                  disabled={loading || !orgName.trim()}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium px-8 py-2 rounded-lg transition-colors"
                >
                  {loading ? 'Creating...' : 'Continue →'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Workspace Step */}
        {step === 'workspace' && organization && (
          <div className="bg-white rounded-lg shadow-xl p-8">
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-2xl font-bold text-gray-900">Create Workspace</h2>
                <span className="text-sm text-gray-500">Step 2 of 2</span>
              </div>
              <p className="text-gray-600">
                Creating workspace in: <span className="font-semibold">{organization.name}</span>
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <label
                  htmlFor="workspace-name"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Workspace Name *
                </label>
                <input
                  id="workspace-name"
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  placeholder="e.g., Engineering, Personal Projects, Default"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Workspaces help organize conversations by team or project
                </p>
              </div>

              <div>
                <label
                  htmlFor="workspace-slug"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  URL Slug
                  <span
                    className="ml-2 text-gray-400 cursor-help"
                    title="A URL-friendly identifier used in web addresses. Auto-generated from your name but you can customize it."
                  >
                    ⓘ
                  </span>
                </label>
                <input
                  id="workspace-slug"
                  type="text"
                  value={workspaceSlug}
                  onChange={(e) => setWorkspaceSlug(e.target.value)}
                  placeholder="e.g., engineering"
                  pattern="[a-z0-9-]+"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Used in URLs - lowercase, no spaces (auto-generated)
                </p>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              <div className="flex justify-between pt-4">
                <button
                  onClick={() => {
                    setStep('organization');
                    setError(null);
                  }}
                  className="px-6 py-2 text-gray-700 hover:text-gray-900 transition-colors"
                >
                  ← Back
                </button>
                <button
                  onClick={handleCreateWorkspace}
                  disabled={loading || !workspaceName.trim()}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium px-8 py-2 rounded-lg transition-colors"
                >
                  {loading ? 'Creating...' : 'Complete Setup →'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Step */}
        {step === 'success' && organization && workspace && (
          <div className="bg-white rounded-lg shadow-xl p-8 text-center">
            <div className="mb-6">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-12 h-12 text-green-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h2 className="text-3xl font-bold text-gray-900 mb-2">Setup Complete!</h2>
              <p className="text-gray-600">
                Your workspace is ready to start ingesting conversations.
              </p>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-8 text-left">
              <h3 className="font-semibold text-gray-900 mb-3">What you created:</h3>
              <dl className="space-y-2">
                <div className="flex items-center">
                  <dt className="text-sm text-gray-600 w-32">Organization:</dt>
                  <dd className="text-sm font-medium text-gray-900">{organization.name}</dd>
                </div>
                <div className="flex items-center">
                  <dt className="text-sm text-gray-600 w-32">Workspace:</dt>
                  <dd className="text-sm font-medium text-gray-900">{workspace.name}</dd>
                </div>
              </dl>
            </div>

            <button
              onClick={handleComplete}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 py-3 rounded-lg transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
