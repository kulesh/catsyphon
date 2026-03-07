# Preceptor Platform Roadmap

**Date**: 2026-02-23
**Companion**: [Preceptor Platform Analysis](preceptor-platform-analysis.md)

---

## Overview

This roadmap closes the gaps identified in the analysis document, transforming CatSyphon + AIObscura from a conversation log analysis tool into a **preceptor platform** for AI-assisted software engineering education.

Four phases, each delivering standalone value. Each phase produces a testable, deployable increment.

```
Phase 0          Phase 1            Phase 2             Phase 3
Foundation ────► Observation ─────► Intervention ──────► Growth

Connect the      See what's         Act on what          Track progress
two tools        happening          you see              over time
```

---

## Phase 0: Foundation

**Goal**: Connect AIObscura and CatSyphon end-to-end. Model preceptor-mentee relationships.

### 0.1 Collector End-to-End Integration [G-AO-1]

**Repo**: AIObscura

The collector client (`aiobscura-core/src/collector/`) is built but untested against a live CatSyphon instance.

- [ ] Integration test suite: aiobscura → CatSyphon Collector Events API
- [ ] Handle edge cases: network interruption recovery, large session batching, sequence gap resolution
- [ ] User documentation: setup guide, configuration reference, troubleshooting
- [ ] `aiobscura-collector` binary: one-shot sync and watch mode
- [ ] Verify semantic parity: sessions ingested via collector match direct-ingestion fidelity

**Acceptance**: An EiC developer runs `aiobscura` locally. Their sessions appear in CatSyphon's web UI within 60 seconds. Killing and restarting aiobscura resumes cleanly from the last sequence.

### 0.2 Preceptor-Mentee Data Model [G-CS-1]

**Repo**: CatSyphon

Introduce first-class mentoring relationships.

```
┌──────────────────────────────────┐
│       preceptor_assignments      │
├──────────────────────────────────┤
│ id: UUID                         │
│ workspace_id: FK → workspaces    │
│ preceptor_id: FK → developers    │
│ mentee_id: FK → developers       │
│ started_at: timestamp            │
│ ended_at: timestamp (nullable)   │
│ learning_goals: JSONB            │
│ status: active | completed       │
│ notes: text                      │
└──────────────────────────────────┘
```

- [ ] Database model and migration
- [ ] Repository with CRUD operations
- [ ] API endpoints: `POST/GET/PATCH /preceptor-assignments`
- [ ] Scoped queries: "show me only my mentees' conversations"
- [ ] Frontend: preceptor assignment management page
- [ ] Frontend: preceptor dashboard with mentee session list
- [x] Foundation in place: workspace/developer/conversation data model and workspace-scoped auth

**Acceptance**: A senior engineer is assigned 3 mentees. Their dashboard shows only those mentees' sessions, filterable by date, project, outcome, and sentiment.

### 0.3 Tagging on Collector API Path [Existing Gap]

**Repo**: CatSyphon

Status audit (2026-02-23): collector-ingested sessions are queued for async tagging on session completion. Remaining gaps are backfill/SLO validation and operational hardening.

- [x] Post-ingestion async tagging job for collector-ingested sessions
- [ ] Backfill mechanism for previously untagged sessions

**Acceptance**: Sessions arriving via aiobscura collector are tagged with sentiment, intent, and outcome within 5 minutes of ingestion.

---

## Phase 1: Observation

**Goal**: Give preceptors and individuals visibility into *how well* the developer steers AI, not just *what* happened.

**Dependency**: Phase 0 complete (data flowing, relationships modeled, tagging operational).

### 1.1 AI Interaction Quality Score [G-AO-2]

**Repo**: AIObscura

Analytics plugin that scores each session on steering quality.

Signals:
- **Prompt specificity**: vague ("fix the bug") vs precise ("the race condition in `sync.go:142` between the mutex release and channel send")
- **Correction frequency**: how often the developer redirected the AI
- **Challenge rate**: how often the developer questioned AI output
- **Oversight depth**: did they read AI-generated code or blindly accept?
- **Outcome independence**: did they solve problems the AI couldn't?

- [ ] `QualityScorePlugin` implementing `AnalyticsPlugin` trait
- [ ] Per-session and rolling-average scores
- [ ] TUI integration: quality score column in threads view
- [ ] Export quality scores via collector events to CatSyphon

**Acceptance**: After a week of use, a developer sees their quality score trend: "Your average steering quality improved from 0.3 to 0.6 this month."

### 1.2 Misconception Detection [G-CS-2]

**Repo**: CatSyphon

LLM-powered post-ingestion analysis identifying when an EiC accepted a known anti-pattern.

Taxonomy (initial):
- Masked concurrency bug (sleep/retry instead of proper synchronization)
- Security bypass accepted (disabled auth, hardcoded credentials, SQL injection)
- Performance anti-pattern (N+1 queries, unbounded memory, missing indexes)
- Brittle test (hardcoded values, time-dependent, order-dependent)
- Architecture violation (circular dependency, layer bypass, god object)

- [ ] Anti-pattern taxonomy as configurable skill definition (ADR-008 aligned)
- [ ] LLM analysis prompt: given conversation + taxonomy → detected misconceptions
- [ ] Store misconceptions in session metadata (JSONB `extra_data`)
- [ ] API endpoint: `GET /conversations/{id}/misconceptions`
- [ ] Frontend: misconception badges on session cards

**Acceptance**: The Figure 1 scenario from the article (sleep-to-mask-race-condition) is detected and labeled "masked concurrency bug" with a link to the specific message where the anti-pattern was accepted.

### 1.3 Skill Domain Mapping [G-AO-3]

**Repo**: AIObscura

Auto-classify sessions by engineering skill domain.

Domains (initial):
- Concurrency & synchronization
- API design & HTTP
- Testing & test design
- Security & authentication
- Performance & optimization
- Data modeling & databases
- Error handling & resilience
- Build systems & CI/CD
- Frontend & UI
- DevOps & infrastructure

- [ ] `SkillDomainPlugin` implementing `AnalyticsPlugin` trait
- [ ] Classification based on: tool calls, file paths, message content, error types
- [ ] Per-session primary and secondary domain tags
- [ ] TUI: domain filter in threads view
- [ ] Coverage heatmap: which domains has this developer practiced?

**Acceptance**: A developer's TUI shows "You've spent 80% of sessions in API design and 0% in concurrency. Consider pairing with your preceptor on concurrent code."

### 1.4 Teachable Moment Extraction [G-CS-3]

**Repo**: CatSyphon

Flag sessions containing learning opportunities for preceptor review.

Criteria:
- Session contains a detected misconception (from 1.2)
- Developer accepted AI code without modification on a non-trivial task
- Session was abandoned after extended struggle (>30 min, frustrated sentiment)
- AI and developer disagreed, and the outcome was ambiguous
- Developer corrected the AI on a subtle issue (positive teachable moment)

- [ ] Teachable moment classifier (skill under ADR-008)
- [ ] Store as session annotations with category and severity
- [ ] Preceptor dashboard: "Sessions to Review This Week" widget
- [ ] Prioritization: severity + recency + domain gap for the mentee

**Acceptance**: A preceptor logs in and sees "3 sessions to review" with the most important first. Each links to the specific moment in the conversation.

---

## Phase 2: Intervention

**Goal**: Enable preceptors to act on observations. Enable individuals to self-correct.

**Dependency**: Phase 1 complete (quality scores, misconceptions, and teachable moments flowing).

### 2.1 Proactive Alerts [G-CS-7]

**Repo**: CatSyphon

Notify preceptors when intervention is needed.

Alert types:
- Mentee stuck on same task >30 minutes with declining sentiment
- Misconception detected in active session (real-time via collector events)
- Session abandoned after extended struggle
- Dangerous anti-pattern accepted (security, data loss)
- Mentee hasn't had a session in >3 days (disengagement signal)

- [ ] Alert rule engine (configurable per preceptor assignment)
- [ ] Delivery channels: in-app notification, webhook (Slack/email integration)
- [ ] Alert fatigue management: cooldown periods, severity thresholds
- [ ] Preceptor notification preferences API

**Acceptance**: A preceptor receives a Slack message: "Alex accepted a SQL injection vulnerability in project-auth session 15 minutes ago. [Review →]"

### 2.2 Self-Coaching Recommendations [G-AO-4]

**Repo**: AIObscura

Evidence-based nudges in the TUI based on quality score trends and skill domain gaps.

- [ ] Recommendation engine based on: quality score trend, domain coverage gaps, recurring misconceptions, peer benchmarks (when available)
- [ ] TUI: recommendations panel in dashboard view
- [ ] Examples: "You've accepted every AI-generated test without modification for 2 weeks. Try writing tests manually." / "Your concurrency domain coverage is 0%. Your project has concurrent code in worker.go — pair with your preceptor."
- [ ] Dismissable with optional feedback ("helpful" / "not relevant")

**Acceptance**: An EiC opens AIObscura and sees 2-3 actionable recommendations based on their recent sessions.

### 2.3 Reasoning Capture and Highlight [G-AO-5]

**Repo**: AIObscura

Make developer reasoning visible as first-class artifacts.

Decision moment types:
- **Redirection**: Developer told the AI to take a different approach
- **Correction**: Developer identified and fixed an AI error
- **Challenge**: Developer questioned AI's reasoning
- **Design choice**: Developer made an architectural decision
- **Acceptance**: Developer accepted AI output (with or without review)

- [ ] Decision moment classifier (heuristic + optional LLM)
- [ ] Annotate messages in local database
- [ ] TUI: decision moment markers in thread detail view
- [ ] Include decision moments in collector events to CatSyphon

**Acceptance**: In the thread detail view, decision moments are highlighted with icons: redirect, correction, challenge, design choice. A preceptor reviewing the session in CatSyphon sees the same markers.

---

## Phase 3: Growth

**Goal**: Track learning trajectories over time. Enable organizational measurement of preceptor program effectiveness.

**Dependency**: Phase 2 complete (interventions flowing, reasoning captured).

### 3.1 Longitudinal Learning Metrics [G-CS-4]

**Repo**: CatSyphon

Time-series tracking of developer growth.

Metrics:
- Quality score trend (from AIObscura via collector)
- Misconception frequency by domain (declining = learning)
- Correction-to-acceptance ratio over time
- Independent problem-solving rate (sessions without misconceptions)
- Skill domain coverage breadth and depth

- [ ] Time-series storage for developer metrics (weekly aggregation)
- [ ] API: `GET /developers/{id}/progression?period=weekly`
- [ ] Frontend: learning trajectory charts in preceptor dashboard
- [ ] Milestone markers: "Week 8: first session with zero misconceptions in concurrency"

**Acceptance**: A preceptor sees a chart showing their mentee's quality score rising from 0.3 to 0.7 over 12 weeks, with misconception frequency declining from 4/week to 1/week.

### 3.2 Comparison Analytics [G-CS-6]

**Repo**: CatSyphon

Anonymized cohort analytics for calibration.

- [ ] Cohort definition: group developers by experience level, team, or custom tag
- [ ] Aggregate metrics per cohort: avg quality score, misconception rate, domain coverage
- [ ] API: `GET /analytics/cohorts?group_by=experience_level`
- [ ] Frontend: cohort comparison charts
- [ ] Privacy: minimum cohort size (5+) to prevent de-anonymization

**Acceptance**: A preceptor sees "Your mentee's quality score (0.5) is at the 40th percentile for EiC developers with 3 months experience. The median is 0.6."

### 3.3 Anonymized Peer Benchmarks [G-AO-7]

**Repo**: AIObscura (client) + CatSyphon (API)

Feed anonymized benchmarks back to individuals.

- [ ] CatSyphon API: `GET /analytics/benchmarks?experience_months=6`
- [ ] AIObscura: fetch benchmarks on sync and display in TUI
- [ ] Opt-in only (requires collector enabled + explicit consent)
- [ ] Display: "Developers at your experience level typically have a quality score of X"

**Acceptance**: An EiC sees in their TUI: "Your quality score: 0.5. Peers at 6 months: median 0.6, 75th percentile 0.8."

### 3.4 Exportable Progress Reports [G-AO-6]

**Repo**: AIObscura

Bridge between personal tool and preceptor meetings.

- [ ] `aiobscura report --period monthly --format md`
- [ ] Contents: quality score trend, skill domains practiced, decision moments summary, recommendations status, self-assessment notes
- [ ] JSON export for programmatic consumption
- [ ] Optional: push to CatSyphon as mentee self-report

**Acceptance**: Before a 1:1 with their preceptor, an EiC runs `aiobscura report --period monthly` and shares the Markdown output.

### 3.5 Preceptor Reporting [G-CS-9]

**Repo**: CatSyphon

Weekly mentee report for preceptors.

- [ ] Automated weekly digest per preceptor assignment
- [ ] Contents: mentee quality score delta, sessions reviewed vs flagged, misconceptions by domain, learning goal progress, recommended focus areas
- [ ] Delivery: in-app + email
- [ ] Program-level report for leadership: aggregate mentee progression, preceptor effectiveness, program ROI metrics
- [x] Foundation in place: workspace-level weekly digest generation and storage (`/digests/weekly`)

**Acceptance**: Every Monday, a preceptor receives an email: "Weekly Report for 3 mentees: Alex improved in testing (quality +0.1), Sam needs attention on security (2 misconceptions), Jordan is on track."

### 3.6 Fine-Grained Access Control [G-CS-8]

**Repo**: CatSyphon

Role-based access for psychological safety.

- [ ] Roles: `admin`, `team_lead`, `preceptor`, `mentee`, `developer`
- [ ] Scoping rules:
  - `preceptor`: sees only assigned mentees' sessions
  - `mentee`: sees own data + anonymized benchmarks
  - `team_lead`: sees aggregate metrics only, no individual sessions
  - `admin`: full access
- [ ] Session privacy flag: mentee can mark sessions as private (excluded from preceptor view)
- [ ] Audit log: who accessed what session data

**Acceptance**: An EiC marks a frustrating debugging session as private. Their preceptor's dashboard doesn't show it, but aggregate metrics still include it anonymously.

---

## Cross-Repo Dependency Map

```
AIObscura                              CatSyphon
─────────                              ─────────

Phase 0:                               Phase 0:
  0.1 Collector E2E ──────────────────►  (receives events)
                                         0.2 Preceptor-Mentee Model
                                         0.3 Tagging on Collector Path

Phase 1:                               Phase 1:
  1.1 Quality Score Plugin               1.2 Misconception Detection
  1.3 Skill Domain Plugin                1.4 Teachable Moment Extraction
       │                                      │
       │ (scores sent via collector)           │
       └─────────────────────────────────►    │
                                              │
Phase 2:                               Phase 2:
  2.2 Self-Coaching                      2.1 Proactive Alerts
  2.3 Reasoning Capture ────────────────► (decision moments in events)

Phase 3:                               Phase 3:
  3.3 Peer Benchmarks ◄────────────────  3.2 Comparison Analytics (API)
  3.4 Progress Reports                   3.1 Longitudinal Metrics
                                         3.5 Preceptor Reporting
                                         3.6 Access Control
```

**Critical path**: Phase 0 items are serial prerequisites. Everything else can be parallelized within phases, with the cross-repo dependencies shown above.

---

## Relationship to Skill-Native Analytics (ADR-008)

The skill-native analytics architecture is the implementation substrate for CatSyphon preceptor features. Specifically:

| Preceptor Feature | Skill-Native Alignment |
|-------------------|------------------------|
| Misconception Detection (1.2) | Implemented as a certified skill with anti-pattern taxonomy as skill configuration |
| Teachable Moment Extraction (1.4) | Skill that composes misconception output + session metadata |
| Proactive Alerts (2.1) | Alert rules as skill bindings with workspace-level customization |
| Longitudinal Metrics (3.1) | Aggregation skill producing weekly metric snapshots |
| Preceptor Reports (3.5) | Report-generating skill composing multiple metric skills |

This means: **Phase 1-3 preceptor features are blocked by skill-native runtime (ADR-008 Phases 1-2).** The roadmap assumes skill-native foundation is built first or in parallel.

Alternative: implement preceptor features as hardcoded analytics first, then migrate to skills when the runtime is ready. This trades architectural purity for speed-to-value. Acceptable if the preceptor platform needs to ship before the skill runtime is complete.

---

## Success Metrics

How we know the platform is working:

| Metric | Target | Measures |
|--------|--------|----------|
| Collector adoption | >80% of team developers syncing | Foundation reach |
| Preceptor session review rate | >3 sessions reviewed per mentee per week | Preceptor engagement |
| Misconception detection precision | >70% true positive rate | Observation quality |
| Quality score improvement | Measurable improvement within 8 weeks of enrollment | Learning effectiveness |
| Alert-to-intervention time | <4 hours from alert to preceptor action | Intervention speed |
| Mentee satisfaction | >4/5 on "my preceptor helps me grow" survey | Program effectiveness |
| Misconception recurrence rate | Declining over time per mentee | Knowledge retention |
