/**
 * API client for setup and onboarding endpoints.
 */

import { API_BASE_URL } from './api';

// ===== Types =====

export interface SetupStatus {
  needs_onboarding: boolean;
  organization_count: number;
  workspace_count: number;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface OrganizationCreate {
  name: string;
  slug?: string;
}

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface WorkspaceCreate {
  organization_id: string;
  name: string;
  slug?: string;
}

// ===== API Functions =====

/**
 * Check if the system needs onboarding.
 *
 * Returns setup status including whether onboarding is needed.
 */
export async function checkSetupStatus(): Promise<SetupStatus> {
  const response = await fetch(`${API_BASE_URL}/setup/status`);

  if (!response.ok) {
    throw new Error(`Failed to check setup status: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new organization.
 *
 * @param data Organization data
 * @returns Created organization
 */
export async function createOrganization(
  data: OrganizationCreate
): Promise<Organization> {
  const response = await fetch(`${API_BASE_URL}/setup/organizations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create organization: ${response.statusText}`);
  }

  return response.json();
}

/**
 * List all organizations.
 *
 * @returns Array of organizations
 */
export async function listOrganizations(): Promise<Organization[]> {
  const response = await fetch(`${API_BASE_URL}/setup/organizations`);

  if (!response.ok) {
    throw new Error(`Failed to list organizations: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a single organization by ID.
 *
 * @param id Organization ID
 * @returns Organization
 */
export async function getOrganization(id: string): Promise<Organization> {
  const response = await fetch(`${API_BASE_URL}/setup/organizations/${id}`);

  if (!response.ok) {
    throw new Error(`Failed to get organization: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Create a new workspace.
 *
 * @param data Workspace data
 * @returns Created workspace
 */
export async function createWorkspace(
  data: WorkspaceCreate
): Promise<Workspace> {
  const response = await fetch(`${API_BASE_URL}/setup/workspaces`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to create workspace: ${response.statusText}`);
  }

  return response.json();
}

/**
 * List all workspaces.
 *
 * @param organizationId Optional organization ID to filter by
 * @returns Array of workspaces
 */
export async function listWorkspaces(
  organizationId?: string
): Promise<Workspace[]> {
  const url = organizationId
    ? `${API_BASE_URL}/setup/workspaces?organization_id=${organizationId}`
    : `${API_BASE_URL}/setup/workspaces`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Failed to list workspaces: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a single workspace by ID.
 *
 * @param id Workspace ID
 * @returns Workspace
 */
export async function getWorkspace(id: string): Promise<Workspace> {
  const response = await fetch(`${API_BASE_URL}/setup/workspaces/${id}`);

  if (!response.ok) {
    throw new Error(`Failed to get workspace: ${response.statusText}`);
  }

  return response.json();
}

// ===== Helper Functions =====

/**
 * Generate a URL-friendly slug from a name.
 *
 * @param name The name to convert to a slug
 * @returns URL-friendly slug (lowercase, hyphens instead of spaces)
 *
 * @example
 * generateSlug("ACME Corporation") // => "acme-corporation"
 * generateSlug("My  Company!!!") // => "my-company"
 */
export function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[\s_]+/g, '-')      // Replace spaces and underscores with hyphens
    .replace(/[^a-z0-9-]/g, '')    // Remove non-alphanumeric characters except hyphens
    .replace(/^-+|-+$/g, '')       // Remove leading/trailing hyphens
    .replace(/-+/g, '-')           // Collapse multiple hyphens
    || 'default';                  // Fallback if empty
}
