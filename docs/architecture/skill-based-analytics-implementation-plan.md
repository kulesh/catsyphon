# Skill-Based Analytics Implementation Plan

Status: Draft  
Owner: Platform + Product Engineering  
Last updated: 2026-02-12

## 1. Purpose

This document defines the implementation sequence for migrating CatSyphon analytics from hardcoded codepaths to a skill-native runtime, consistent with:

- `docs/architecture/skill-based-analytics-product-spec.md`

The plan is phased to keep production stable while progressively switching surfaces (Weekly Digest, AI Insights, dashboard analytics) to skill bindings.

## 2. Program Outcomes

By completion:

1. All analytics experiences are produced by bound skills.
2. Default built-in skill packs ship with CatSyphon.
3. Workspaces can safely install and configure additional skills.
4. Certification and provenance are mandatory for production skill outputs.

## 3. Streams of Work

Implementation runs across five concurrent streams.

## 3.1 Domain and Data Model Stream

- Introduce Skill, SkillVersion, SkillRun, SkillArtifact, SkillBinding, SkillCertification, SkillSchedule, CapabilityPolicy entities.

## 3.2 Runtime and Policy Stream

- Build skill runtime engine, operator framework, policy enforcement, scheduling.

## 3.3 Analytics Surface Migration Stream

- Migrate Weekly Digest, AI Insights, and dashboard modules to skill bindings.

## 3.4 Tooling and UX Stream

- Build skill catalog, test/certify/promote UI, and provenance UX.

## 3.5 Reliability and Governance Stream

- Introduce observability, quotas, approval workflows, and audit trail.

## 4. Dependencies and Preconditions

1. Stable semantic layer for metrics/dimensions required by analytics.
2. Existing ingestion and core telemetry schema remains authoritative.
3. Background job and scheduling infrastructure available for run orchestration.
4. Multi-tenant authorization model must be reused by skill policies.

## 5. Phase Plan

## Phase 0: Foundation and Design Freeze

Objective:
- Lock domain language and contracts before implementation fan-out.

Deliverables:
1. ADR: Skill-native analytics architecture decision.
2. Final manifest schema (v1).
3. Operator contract specification (inputs, outputs, error model).
4. Capability policy matrix.

Exit Criteria:
1. Cross-team agreement on runtime scope and non-goals.
2. Schema versions tagged and frozen for v1.

## Phase 1: Data Model and Repository Layer

Objective:
- Add first-class storage model for skill lifecycle and runtime artifacts.

Deliverables:
1. DB migrations for:
- `skills`
- `skill_versions`
- `skill_bindings`
- `skill_runs`
- `skill_artifacts`
- `skill_certifications`
- `skill_schedules`
- `skill_capability_policies`
2. Repository interfaces and tests.
3. Referential integrity and tenancy constraints.

Exit Criteria:
1. CRUD and query tests passing for all new entities.
2. Migration rollback/forward validated in local stack.

## Phase 2: Skill Runtime Kernel (Trusted Core)

Objective:
- Build execution engine and policy enforcement.

Deliverables:
1. Manifest parser + validator.
2. Operator execution pipeline with typed boundaries.
3. Policy engine (capability checks per step).
4. Run lifecycle state machine:
- `queued -> running -> succeeded | failed | canceled`
5. Artifact persistence and lineage metadata.

Exit Criteria:
1. End-to-end execution works for deterministic sample skills.
2. Failed runs produce complete diagnostics and lineage.

## Phase 3: Certification and Correctness Gates

Objective:
- Enforce reliability before skills become production-visible.

Deliverables:
1. Fixture-based skill test harness.
2. Regression comparison framework (baseline vs candidate).
3. Certification workflow and persistence.
4. Promotion eligibility checks.

Exit Criteria:
1. Uncertified skill versions cannot be promoted.
2. Certification result visible in API and UI.

## Phase 4: Built-In Skill Pack Migration

Objective:
- Convert existing hardcoded analytics to internal skills with parity.

Deliverables:
1. Built-in `weekly_digest` skill pack:
- Overview section
- Risk section
- Velocity section
- Actionable recommendations
2. Built-in `ai_insights` skill pack:
- Conversation insights
- Project insights
- Recommendation modules
3. Built-in dashboard analytics skills for current metrics cards.
4. Backward-compatible API facades mapping old endpoints to skill outputs.

Exit Criteria:
1. Legacy and skill-based outputs are parity-tested within defined tolerances.
2. Existing UI remains functional with no behavior regression.

## Phase 5: UI and Product Surface Transition

Objective:
- Make skill lifecycle and provenance visible to users.

Deliverables:
1. Skill Catalog page.
2. Skill detail page with versions, config, certification, run history.
3. Bindings management UI for digest/insights/dashboard.
4. Provenance badge on every analytics artifact.

Exit Criteria:
1. Admin can install, configure, test, and promote built-in skills.
2. End users can see which skill version generated each output.

## Phase 6: Custom Skill Enablement (Governed)

Objective:
- Allow workspace-specific customization without code deploy.

Deliverables:
1. Workspace skill upload/install flow (manifest-only in v1).
2. Capability assignment and policy validation.
3. Quotas for runs, runtime, and LLM budgets.
4. Rollback controls.

Exit Criteria:
1. Workspace custom skills can run in staging and production channels.
2. Policy denials and quota violations are observable and auditable.

## Phase 7: Full Cutover and Legacy Removal

Objective:
- Remove hardcoded analytics execution paths.

Deliverables:
1. Legacy codepath deprecation flags removed.
2. Endpoints/services internally routed exclusively through skill runtime.
3. Documentation updates and runbooks.

Exit Criteria:
1. 100% analytics surfaces use skill bindings.
2. No active dependencies on removed hardcoded modules.

## 6. Technical Work Breakdown

## 6.1 Backend Components

New modules (proposed):

1. `backend/src/catsyphon/skills/models.py`
2. `backend/src/catsyphon/skills/manifests.py`
3. `backend/src/catsyphon/skills/runtime.py`
4. `backend/src/catsyphon/skills/operators/`
5. `backend/src/catsyphon/skills/policy.py`
6. `backend/src/catsyphon/skills/certification.py`
7. `backend/src/catsyphon/api/routes/skills.py`
8. `backend/src/catsyphon/api/routes/skill_runs.py`

## 6.2 Frontend Components

New modules (proposed):

1. `frontend/src/pages/Skills/SkillCatalog.tsx`
2. `frontend/src/pages/Skills/SkillDetail.tsx`
3. `frontend/src/pages/Skills/SkillRuns.tsx`
4. `frontend/src/components/skills/ProvenanceBadge.tsx`
5. `frontend/src/components/skills/CertificationStatus.tsx`

## 6.3 Data/Schema

1. Alembic revisions for skill tables.
2. Indexing for run history queries and artifact retrieval.
3. Retention policy for run logs and artifacts.

## 7. Testing Strategy

## 7.1 Unit Testing

1. Manifest schema validation.
2. Operator contract enforcement.
3. Policy evaluation logic.

## 7.2 Integration Testing

1. End-to-end skill run with deterministic operators.
2. Failure paths and retries.
3. Certification gating and promotion flow.

## 7.3 Regression Testing

1. Weekly Digest legacy vs skill output comparisons.
2. AI Insights legacy vs skill output comparisons.
3. Dashboard metric parity checks.

## 7.4 Acceptance Testing

1. Admin lifecycle:
- install -> configure -> test -> certify -> promote
2. Rollback and re-run.
3. Provenance visibility on generated artifacts.

## 8. Operational Readiness

## 8.1 Observability

Add dashboards for:

1. Run success rate and latency by skill.
2. Top failing skills/operators.
3. Artifact freshness SLA.
4. LLM cost per skill.

## 8.2 Runbooks

1. Skill run incident response.
2. Certification failure triage.
3. Emergency rollback procedure.

## 8.3 Alerting

1. Failure rate threshold alerts.
2. Freshness lag alerts.
3. Budget/usage threshold alerts.

## 9. Rollout Strategy

## 9.1 Progressive Rollout

1. Internal-only skill runtime (hidden).
2. Shadow runs for built-in skills (compare only).
3. Controlled read-path switch for selected workspaces.
4. Broad rollout by surface:
- Weekly Digest
- AI Insights
- Dashboard analytics
5. Enable custom skills after platform stability SLOs are met.

## 9.2 Rollback Strategy

1. Keep legacy path behind feature flags until Phase 7 complete.
2. Per-surface failback toggle.
3. Per-skill version rollback to last certified version.

## 10. Milestones and Gates

Milestone A:
- Phases 0-2 complete (runtime kernel functional).

Milestone B:
- Phase 3 complete (certification enforced).

Milestone C:
- Phase 4 complete (built-in skill parity).

Milestone D:
- Phase 5 complete (UI and provenance complete).

Milestone E:
- Phases 6-7 complete (custom enablement + legacy removal).

## 11. Risks and Mitigations

1. Risk: Semantic metric inconsistency across skills  
Mitigation: Metric contracts and shared semantic views only.

2. Risk: Skill runtime complexity growth  
Mitigation: Minimal operator set in v1, strict interface boundaries.

3. Risk: LLM nondeterminism reducing trust  
Mitigation: Deterministic operators for numeric outputs, LLM constrained to narrative layers.

4. Risk: Governance overhead for admins  
Mitigation: Sensible defaults, templates, and built-in certified skill packs.

## 12. Documentation Deliverables

1. User docs:
- Skill catalog usage.
- Certification and promotion workflow.

2. Operator reference docs:
- Input/output contracts and examples.

3. Admin docs:
- Policy model, quotas, and rollback.

4. Architecture updates:
- Main architecture map including skill runtime context.

## 13. Completion Definition

This program is complete when:

1. All analytics outputs are skill-bound.
2. Legacy hardcoded analytics execution is removed.
3. Certification/provenance is mandatory and visible.
4. Workspace custom skills are safely supported under capability policies.
5. Stability and freshness SLOs are met for two consecutive release cycles.

