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

  // Related counts
  message_count: number;
  epoch_count: number;
  files_count: number;

  // Related objects (optional)
  project?: ProjectResponse;
  developer?: DeveloperResponse;
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageResponse[];
  epochs: EpochResponse[];
  files_touched: FileTouchedResponse[];
  conversation_tags: ConversationTagResponse[];
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
