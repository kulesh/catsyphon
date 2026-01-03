/**
 * TypeScript types matching backend Pydantic schemas.
 *
 * Generated from: backend/src/catsyphon/api/schemas.py
 */

// Using `any` for flexible JSON structures from the API is intentional.
// These fields contain variable data that TypeScript cannot statically type.
/* eslint-disable @typescript-eslint/no-explicit-any */

// ===== Base Types =====

export interface ProjectBase {
  name: string;
  description: string | null;
}

export interface ProjectResponse extends ProjectBase {
  id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem extends ProjectResponse {
  directory_path: string;
  session_count: number;
  last_session_at: string | null;
}

export interface DeveloperBase {
  username: string;
  email: string | null;
}

export interface DeveloperResponse extends DeveloperBase {
  id: string;
  extra_data: Record<string, any>;
  created_at: string;
}

// ===== Conversation Types =====

export interface MessageResponse {
  id: string;
  role: string | null;  // null for non-conversational messages (summary, system events, etc.)
  content: string;
  thinking_content: string | null;
  timestamp: string;
  sequence: number;
  tool_calls: Array<Record<string, any>>;
  tool_results: Array<Record<string, any>>;
  code_changes: Array<Record<string, any>>;
  entities: Record<string, any>;
  extra_data: Record<string, any>;

  // Extracted from extra_data for convenience
  model: string | null;  // Claude model used (e.g., "claude-opus-4-5")
  token_usage: TokenUsage | null;  // Token usage breakdown
  stop_reason: string | null;  // end_turn, max_tokens, tool_use
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  cache_creation_tokens?: number;
  cache_read_tokens?: number;
}

export interface EpochResponse {
  id: string;
  sequence: number;
  intent: string | null;
  outcome: string | null;
  sentiment: string | null;
  sentiment_score: number | null;
  start_time: string;
  end_time: string | null;
  duration_seconds: number | null;
  extra_data: Record<string, any>;
  message_count: number;
}

export interface FileTouchedResponse {
  id: string;
  file_path: string;
  change_type: string | null;
  lines_added: number;
  lines_deleted: number;
  lines_modified: number;
  timestamp: string;
  extra_data: Record<string, any>;
}

export interface ConversationListItem {
  id: string;
  project_id: string | null;
  developer_id: string | null;
  agent_type: string;
  agent_version: string | null;
  start_time: string;
  end_time: string | null;
  status: string;
  success: boolean | null;
  iteration_count: number;
  tags: Record<string, any>;
  extra_data: Record<string, any>;
  created_at: string;
  updated_at: string;

  // Hierarchy fields (Phase 2: Epic 7u2)
  parent_conversation_id: string | null;
  conversation_type: string;
  context_semantics: Record<string, any>;
  agent_metadata: Record<string, any>;

  // Related counts
  message_count: number;
  epoch_count: number;
  files_count: number;
  children_count: number;
  depth_level: number; // Hierarchy depth: 0 for parent, 1 for child
  plan_count: number; // Number of plans in this conversation

  // Extracted from extra_data for convenience
  slug: string | null; // Human-readable session name (e.g., "sprightly-dancing-liskov")
  git_branch: string | null; // Git branch active during session
  total_tokens: number | null; // Sum of all message token usage

  // Related objects (optional)
  project?: ProjectResponse;
  developer?: DeveloperResponse;
}

export interface RawLogInfo {
  id: string;
  file_path: string | null;
  file_hash: string;
  created_at: string;
}

// ===== Plan Types =====

export interface PlanOperation {
  operation_type: string; // 'create' | 'edit' | 'read'
  file_path: string;
  content?: string;
  old_content?: string;
  new_content?: string;
  timestamp?: string;
  message_index: number;
}

export interface PlanResponse {
  plan_file_path: string;
  initial_content?: string;
  final_content?: string;
  status: string; // 'active' | 'approved' | 'abandoned'
  iteration_count: number;
  operations: PlanOperation[];
  entry_message_index?: number;
  exit_message_index?: number;
  related_agent_session_ids: string[];
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageResponse[];
  epochs: EpochResponse[];
  files_touched: FileTouchedResponse[];
  raw_logs: RawLogInfo[];
  plans: PlanResponse[];

  // Hierarchical relationships (Phase 2: Epic 7u2)
  children: ConversationListItem[];
  parent: ConversationListItem | null;

  // Session context from extra_data
  summaries: SummaryInfo[]; // Auto-generated session checkpoints
  compaction_events: CompactionEvent[]; // Context compaction markers
}

// Summary info from Claude Code session summaries
export interface SummaryInfo {
  summary_type: string; // "auto" or "manual"
  summary: string;
  last_user_message_id: string;
  num_exchanges: number;
  timestamp?: string;
}

// Compaction event tracking context window management
export interface CompactionEvent {
  message_index: number;
  timestamp: string;
  pre_tokens?: number;
  post_tokens?: number;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ===== Stats Types =====

export interface OverviewStats {
  total_conversations: number;
  total_messages: number;
  total_projects: number;
  total_developers: number;
  conversations_by_status: Record<string, number>;
  conversations_by_agent: Record<string, number>;
  recent_conversations: number;
  success_rate: number | null;

  // Hierarchical conversation stats (Phase 2: Epic 7u2)
  total_main_conversations: number;
  total_agent_conversations: number;
  conversations_by_type: Record<string, number>;

  // Plan statistics
  total_plans: number;
  plans_by_status: Record<string, number>; // approved, active, abandoned
  conversations_with_plans: number;
}

export interface AgentPerformanceStats {
  agent_type: string;
  total_conversations: number;
  successful_conversations: number;
  failed_conversations: number;
  success_rate: number;
  avg_iteration_count: number;
  avg_duration_minutes: number | null;
}

export interface DeveloperActivityStats {
  developer_id: string;
  developer_username: string;
  total_conversations: number;
  successful_conversations: number;
  total_messages: number;
  total_files_touched: number;
  avg_conversation_duration: number | null;
  most_used_agent: string | null;
}

// ===== Query Parameters =====

export interface ConversationFilters {
  project_id?: string;
  developer_id?: string;
  agent_type?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  success?: boolean;
  page?: number;
  page_size?: number;
}

// ===== Health Check =====

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  database: 'healthy' | 'unhealthy';
}

// ===== Upload Types =====

export interface UploadResult {
  filename: string;
  status: 'success' | 'duplicate' | 'skipped' | 'error';
  conversation_id?: string;
  message_count: number;
  epoch_count: number;
  files_count: number;
  error?: string;
}

export interface UploadResponse {
  success_count: number;
  failed_count: number;
  results: UploadResult[];
}

// ===== Watch Configuration Types =====

export interface WatchConfigurationCreate {
  directory: string;
  project_id?: string | null;
  developer_id?: string | null;
  enable_tagging?: boolean;
  extra_config?: Record<string, any>;
  created_by?: string | null;
}

export interface WatchConfigurationUpdate {
  directory?: string;
  project_id?: string | null;
  developer_id?: string | null;
  enable_tagging?: boolean;
  extra_config?: Record<string, any>;
  is_active?: boolean;
}

export interface WatchConfigurationResponse {
  id: string;
  directory: string;
  project_id: string | null;
  developer_id: string | null;
  enable_tagging: boolean;
  is_active: boolean;
  stats: Record<string, any>;
  extra_config: Record<string, any>;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  last_started_at: string | null;
  last_stopped_at: string | null;
}

export interface WatchStatus {
  total_configs: number;
  active_count: number;
  inactive_count: number;
  active_configs: WatchConfigurationResponse[];
}

// ===== Ingestion Job Types =====

export interface IngestionJobFilters {
  source_type?: 'watch' | 'upload' | 'cli';
  status?: 'success' | 'failed' | 'duplicate' | 'skipped';
  page?: number;
  page_size?: number;
}

export interface IngestionJobResponse {
  id: string;
  source_type: 'watch' | 'upload' | 'cli';
  source_config_id: string | null;
  file_path: string | null;
  raw_log_id: string | null;
  conversation_id: string | null;
  status: 'success' | 'failed' | 'duplicate' | 'skipped' | 'processing';
  error_message: string | null;
  processing_time_ms: number | null;
  incremental: boolean;
  messages_added: number;
  ingest_mode?: string | null;
  started_at: string;
  completed_at: string | null;
  created_by: string | null;
  metrics: Record<string, any>;
}

export interface TimeseriesDataPoint {
  timestamp: string;
  job_count: number;
  avg_processing_time_ms: number | null;
  success_count: number;
  failed_count: number;
}

export interface ProcessingTimePercentiles {
  p50: number | null;
  p75: number | null;
  p90: number | null;
  p99: number | null;
}

export interface IngestionStatsResponse {
  total_jobs: number;
  by_status: Record<string, number>;
  by_source_type: Record<string, number>;
  avg_processing_time_ms: number | null;
  peak_processing_time_ms: number | null;
  processing_time_percentiles: ProcessingTimePercentiles;
  incremental_jobs: number;
  incremental_percentage: number | null;
  incremental_speedup: number | null;
  // Recent activity metrics
  jobs_last_hour: number;
  jobs_last_24h: number;
  processing_rate_per_minute: number;
  // Success/failure metrics
  success_rate: number | null;
  failure_rate: number | null;
  time_since_last_failure_minutes: number | null;
  // Time-series data for sparklines
  timeseries_24h: TimeseriesDataPoint[];
  // Stage-level metrics
  avg_parse_duration_ms: number | null;
  avg_deduplication_check_ms: number | null;
  avg_database_operations_ms: number | null;
  avg_tagging_duration_ms: number | null;
  avg_llm_tagging_ms: number | null;
  avg_llm_prompt_tokens: number | null;
  avg_llm_completion_tokens: number | null;
  avg_llm_total_tokens: number | null;
  avg_llm_cost_usd: number | null;
  total_llm_cost_usd: number | null;
  llm_cache_hit_rate: number | null;
  error_rates_by_stage: Record<string, number>;
}

// ===== Grouped File Types (Frontend Only) =====

export interface GroupedFileOperation {
  change_type: string;
  count: number;
  total_lines_added: number;
  total_lines_deleted: number;
  total_lines_modified: number;
  modifications: FileTouchedResponse[];
}

export interface GroupedFile {
  file_path: string;
  total_operations: number;
  total_lines_added: number;
  total_lines_deleted: number;
  total_lines_modified: number;
  operations: Record<string, GroupedFileOperation>;
}

// ===== Project Analytics Types =====

export interface SentimentTimelinePoint {
  date: string; // ISO date string (YYYY-MM-DD)
  avg_sentiment: number; // Average sentiment score (-1.0 to 1.0)
  session_count: number; // Number of sessions on this date
}

export interface ProjectStats {
  project_id: string;
  session_count: number;
  total_messages: number;
  total_files_changed: number;
  success_rate: number | null;
  avg_session_duration_seconds: number | null;
  first_session_at: string | null;
  last_session_at: string | null;
  top_features: string[];
  top_problems: string[];
  tool_usage: Record<string, number>;
  developer_count: number;
  developers: string[];
  sentiment_timeline: SentimentTimelinePoint[];
}

export interface PairingEffectivenessPair {
  developer: string | null;
  agent_type: string;
  score: number;
  success_rate: number | null;
  lines_per_hour: number | null;
  first_change_minutes: number | null;
  sessions: number;
}

export interface RoleDynamicsSummary {
  agent_led: number;
  dev_led: number;
  co_pilot: number;
}

export interface HandoffStats {
  handoff_count: number;
  avg_response_minutes: number | null;
  success_rate: number | null;
  clarifications_avg: number | null;
}

export interface ImpactMetrics {
  avg_lines_per_hour: number | null;
  median_first_change_minutes: number | null;
  total_lines_changed: number;
  sessions_measured: number;
}

export interface SentimentByAgent {
  agent_type: string;
  avg_sentiment: number | null;
  sessions: number;
}

export interface InfluenceFlow {
  source: string;
  target: string;
  count: number;
}

export interface ErrorBucket {
  agent_type: string;
  category: string;
  count: number;
}

export interface ThinkingTimeStats {
  pair_count: number;
  median_latency_seconds?: number | null;
  p95_latency_seconds?: number | null;
  max_latency_seconds?: number | null;
  pct_with_thinking?: number | null;
  pct_with_tool_calls?: number | null;
}

export interface ProjectAnalytics {
  project_id: string;
  date_range?: string | null;
  pairing_top: PairingEffectivenessPair[];
  pairing_bottom: PairingEffectivenessPair[];
  role_dynamics: RoleDynamicsSummary;
  handoffs: HandoffStats;
  impact: ImpactMetrics;
  sentiment_by_agent: SentimentByAgent[];
  influence_flows: InfluenceFlow[];
  error_heatmap: ErrorBucket[];
  thinking_time?: ThinkingTimeStats | null;
}

export interface ProjectSession {
  id: string;
  start_time: string;
  end_time: string | null;
  last_activity: string | null;  // Actual last message timestamp
  duration_seconds: number | null;
  status: string;
  success: boolean | null;
  message_count: number;
  files_count: number;
  developer: string | null;
  agent_type: string;

  // Hierarchy fields (for hierarchical display)
  children_count: number;
  depth_level: number;
  parent_conversation_id: string | null;

  // Plan fields
  plan_count: number;
  plan_status: 'approved' | 'active' | 'abandoned' | null;
}

export interface ProjectSessionsResponse {
  items: ProjectSession[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ProjectFileAggregation {
  file_path: string;
  modification_count: number;
  total_lines_added: number;
  total_lines_deleted: number;
  last_modified_at: string;
  session_ids: string[];
}

// ===== Canonical Types =====

export interface CanonicalMetadata {
  tools_used: string[];
  files_touched: string[];
  errors_encountered: string[];
  has_errors: boolean;
}

export interface CanonicalConfig {
  canonical_type: string;
  max_tokens: number;
  sampling_strategy: string;
}

export interface CanonicalResponse {
  id: string;
  conversation_id: string;
  version: number;
  canonical_type: string;
  narrative: string;
  token_count: number;
  metadata: CanonicalMetadata;
  config: CanonicalConfig;
  source_message_count: number;
  source_token_estimate: number;
  generated_at: string;
}

export interface CanonicalNarrativeResponse {
  narrative: string;
  token_count: number;
  canonical_type: string;
  version: number;
}

// ===== Insights Types =====

export interface KeyMoment {
  timestamp: string; // "early", "mid", "late"
  event: string; // Description of the event
  impact: string; // "positive", "negative", "neutral"
}

export interface QuantitativeMetrics {
  message_count: number;
  epoch_count: number;
  files_touched_count: number;
  tool_calls_count: number;
  token_count: number;
  has_errors: boolean;
  tools_used: string[];
  child_conversations_count: number;
  duration_seconds: number | null;
}

export interface InsightsResponse {
  conversation_id: string;

  // Qualitative insights from LLM
  workflow_patterns: string[];
  productivity_indicators: string[];
  collaboration_quality: number; // 1-10
  key_moments: KeyMoment[];
  learning_opportunities: string[];
  agent_effectiveness: number; // 1-10
  scope_clarity: number; // 1-10
  technical_debt_indicators: string[];
  testing_behavior: string;
  summary: string;

  // Quantitative metrics
  quantitative_metrics: QuantitativeMetrics;

  // Metadata
  canonical_version: number;
  analysis_timestamp: number;
}

// ===== Project Insights Types =====

export interface PatternFrequency {
  pattern: string;
  count: number;
  percentage: number;
}

export interface TrendPoint {
  date: string; // Week start date (YYYY-MM-DD)
  avg_score: number;
  count: number;
}

export interface ProjectInsightsResponse {
  project_id: string;
  date_range: string;
  conversations_analyzed: number;
  conversations_with_insights: number;

  // Pattern Aggregation
  top_workflow_patterns: PatternFrequency[];
  top_learning_opportunities: PatternFrequency[];
  top_anti_patterns: PatternFrequency[];
  common_technical_debt: PatternFrequency[];

  // Temporal Trends
  collaboration_trend: TrendPoint[];
  effectiveness_trend: TrendPoint[];
  scope_clarity_trend: TrendPoint[];

  // Averages
  avg_collaboration_quality: number;
  avg_agent_effectiveness: number;
  avg_scope_clarity: number;

  // Stats
  total_messages: number;
  total_tool_calls: number;
  success_rate: number | null;

  // LLM Summary (optional)
  summary: string | null;

  // Metadata
  generated_at: number;

  // Cache metadata (for freshness indicators)
  insights_cached: number;
  insights_generated: number;
  insights_failed: number;
  oldest_insight_at: string | null;
  newest_insight_at: string | null;
  latest_conversation_at: string | null;
}

// ===== Health Report Types =====

export interface SessionEvidence {
  session_id: string;
  title: string;
  date: string;
  duration_minutes: number;
  explanation: string;
  outcome: string; // LLM-generated description of what happened and why
}

export interface PatternEvidence {
  description: string;
  data: Record<string, unknown>;
}

export interface HealthReportDiagnosis {
  strengths: string[];
  gaps: string[];
  primary_issue: string | null;
  primary_issue_detail: string | null;
}

export interface HealthReportEvidence {
  success_example: SessionEvidence | null;
  failure_example: SessionEvidence | null;
  patterns: PatternEvidence[];
}

export interface HealthReportRecommendation {
  advice: string;
  evidence: string;
  filter_link?: string;
}

export interface HealthReportResponse {
  score: number;
  label: string;
  summary: string;
  diagnosis: HealthReportDiagnosis;
  evidence: HealthReportEvidence;
  recommendations: HealthReportRecommendation[];
  session_links: Record<string, string>;
  sessions_analyzed: number;
  generated_at: number;
  cached: boolean;
}

// ===== Automation Recommendation Types =====

export interface RecommendationEvidence {
  quotes: string[];
  pattern_count: number;
  // MCP-specific evidence fields
  matched_signals?: string[];
  workarounds_detected?: string[];
  friction_indicators?: string[];
}

export interface SuggestedImplementation {
  // Slash command fields
  command_name?: string;
  trigger_phrases: string[];
  template?: string | null;
  // MCP-specific fields
  category?: string;
  suggested_mcps?: string[];
  use_cases?: string[];
  friction_score?: number;
}

export interface RecommendationResponse {
  id: string;
  conversation_id: string;
  recommendation_type: string; // 'slash_command', 'mcp_server', 'sub_agent'
  title: string;
  description: string;
  confidence: number; // 0.0 to 1.0
  priority: number; // 0=critical, 4=low
  evidence: RecommendationEvidence;
  suggested_implementation: SuggestedImplementation | null;
  status: string; // 'pending', 'accepted', 'dismissed', 'implemented'
  user_feedback: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecommendationListResponse {
  items: RecommendationResponse[];
  total: number;
  conversation_id: string;
}

export interface RecommendationUpdate {
  status?: string;
  user_feedback?: string;
}

export interface DetectionResponse {
  conversation_id: string;
  recommendations_count: number;
  tokens_analyzed: number;
  detection_model: string;
  recommendations: RecommendationResponse[];
}

export interface RecommendationSummaryStats {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  average_confidence: number;
}

export interface BenchmarkItem {
  name: string;
  status: string;
  data: Record<string, any>;
  error?: string | null;
}

export interface BenchmarkAvailabilityResponse {
  enabled: boolean;
  requires_token: boolean;
}

export interface BenchmarkResultResponse {
  run_id: string;
  started_at: string;
  completed_at: string;
  benchmarks: BenchmarkItem[];
  environment: Record<string, any>;
}

export interface BenchmarkStatusResponse {
  status: string;
  run_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
}

export interface ConversationRecapResponse {
  conversation_id: string;
  version: number;
  summary: string;
  key_files: string[];
  blockers: string[];
  next_steps: string[];
  metadata: Record<string, any>;
  canonical_version: number;
  generated_at: string;
}

export interface WeeklyDigestResponse {
  workspace_id: string;
  period_start: string;
  period_end: string;
  version: number;
  summary: string;
  wins: string[];
  blockers: string[];
  highlights: string[];
  metrics: Record<string, any>;
  generated_at: string;
}

export interface WorkflowPatternExample {
  conversation_id: string;
  summary?: string | null;
  outcome?: string | null;
}

export interface WorkflowPatternItem {
  pattern: string;
  count: number;
  success_rate?: number | null;
  examples: WorkflowPatternExample[];
}

export interface WorkflowPatternResponse {
  items: WorkflowPatternItem[];
}
