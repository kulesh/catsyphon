/**
 * TypeScript types matching backend Pydantic schemas.
 *
 * Generated from: backend/src/catsyphon/api/schemas.py
 */

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
  role: string;
  content: string;
  thinking_content: string | null;
  timestamp: string;
  sequence: number;
  tool_calls: Array<Record<string, any>>;
  tool_results: Array<Record<string, any>>;
  code_changes: Array<Record<string, any>>;
  entities: Record<string, any>;
  extra_data: Record<string, any>;
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

export interface ConversationTagResponse {
  id: string;
  tag_type: string;
  tag_value: string;
  confidence: number | null;
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

  // Related objects (optional)
  project?: ProjectResponse;
  developer?: DeveloperResponse;
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageResponse[];
  epochs: EpochResponse[];
  files_touched: FileTouchedResponse[];
  conversation_tags: ConversationTagResponse[];

  // Hierarchical relationships (Phase 2: Epic 7u2)
  children: ConversationListItem[];
  parent: ConversationListItem | null;
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
  status: 'success' | 'error';
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
  started_at: string;
  completed_at: string | null;
  created_by: string | null;
}

export interface IngestionStatsResponse {
  total_jobs: number;
  by_status: Record<string, number>;
  by_source_type: Record<string, number>;
  avg_processing_time_ms: number | null;
  incremental_jobs: number;
  incremental_percentage: number | null;
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
}

export interface ProjectSession {
  id: string;
  start_time: string;
  end_time: string | null;
  duration_seconds: number | null;
  status: string;
  success: boolean | null;
  message_count: number;
  files_count: number;
  developer: string | null;
  agent_type: string;
}

export interface ProjectFileAggregation {
  file_path: string;
  modification_count: number;
  total_lines_added: number;
  total_lines_deleted: number;
  last_modified_at: string;
  session_ids: string[];
}
