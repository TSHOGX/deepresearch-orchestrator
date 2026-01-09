/**
 * TypeScript types matching the Python data models.
 */

// Enums

export type ResearchPhase =
  | "planning"
  | "plan_review"
  | "researching"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type PlanItemStatus = "pending" | "in_progress" | "completed" | "skipped";

export type EventType =
  | "plan_draft"
  | "plan_updated"
  | "phase_change"
  | "agent_started"
  | "agent_progress"
  | "agent_completed"
  | "agent_failed"
  | "checkpoint_saved"
  | "synthesis_started"
  | "synthesis_progress"
  | "report_ready"
  | "error"
  | "heartbeat"
  | "session_cancelled";

// Data Models

export interface PlanItem {
  id: string;
  topic: string;
  description: string;
  scope: string;
  priority: number;
  key_questions: string[];
  suggested_sources: string[];
  status: PlanItemStatus;
}

export interface ResearchPlan {
  understanding: string;
  clarifications: string[];
  plan_items: PlanItem[];
  estimated_time_minutes: number;
  created_at: string;
  modified_at: string;
}

export interface Source {
  url: string | null;
  title: string;
  snippet: string;
  reliability: string;
}

export interface AgentProgress {
  agent_id: string;
  plan_item_id: string;
  topic: string;
  status: AgentStatus;
  current_action: string;
  tool_name: string | null;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface AgentResult {
  agent_id: string;
  plan_item_id: string;
  topic: string;
  findings: string;
  sources: Source[];
  confidence: number;
  raw_notes: string;
  execution_time: number;
  created_at: string;
}

export interface ResearchSession {
  session_id: string;
  user_query: string;
  detected_language: string;
  phase: ResearchPhase;
  plan: ResearchPlan | null;
  agent_progress: Record<string, AgentProgress>;
  agent_results: AgentResult[];
  final_report: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error: string | null;
}

// API Request/Response types

export interface StartResearchRequest {
  query: string;
  language?: string;
}

export interface ConfirmPlanRequest {
  confirmed: boolean;
  modifications?: PlanItem[];
  skip_items?: string[];
}

export interface ResearchSessionResponse {
  session_id: string;
  phase: ResearchPhase;
  plan: ResearchPlan | null;
  agent_progress: Record<string, AgentProgress>;
  completed_agents: number;
  total_agents: number;
  final_report: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: ResearchSession[];
  total: number;
}

export interface ConfigResponse {
  api_host: string;
  api_port: number;
  planner_model: string;
  researcher_model: string;
  synthesizer_model: string;
  max_parallel_agents: number;
  agent_timeout_seconds: number;
  checkpoint_interval_seconds: number;
  log_level: string;
}

export interface ConfigUpdateRequest {
  planner_model?: "opus" | "sonnet" | "haiku";
  researcher_model?: "opus" | "sonnet" | "haiku";
  synthesizer_model?: "opus" | "sonnet" | "haiku";
  max_parallel_agents?: number;
  agent_timeout_seconds?: number;
  checkpoint_interval_seconds?: number;
}

// SSE Event types

export interface BaseEvent {
  event_type: EventType;
  session_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface PlanDraftEvent extends BaseEvent {
  event_type: "plan_draft";
  plan: ResearchPlan;
}

export interface PlanUpdatedEvent extends BaseEvent {
  event_type: "plan_updated";
  plan: ResearchPlan;
}

export interface PhaseChangeEvent extends BaseEvent {
  event_type: "phase_change";
  old_phase: ResearchPhase | null;
  new_phase: ResearchPhase;
}

export interface AgentStartedEvent extends BaseEvent {
  event_type: "agent_started";
  agent_id: string;
  plan_item_id: string;
  topic: string;
}

export interface AgentProgressEvent extends BaseEvent {
  event_type: "agent_progress";
  progress: AgentProgress;
}

export interface AgentCompletedEvent extends BaseEvent {
  event_type: "agent_completed";
  result: AgentResult;
}

export interface AgentFailedEvent extends BaseEvent {
  event_type: "agent_failed";
  agent_id: string;
  error: string;
}

export interface SynthesisStartedEvent extends BaseEvent {
  event_type: "synthesis_started";
  total_results: number;
}

export interface SynthesisProgressEvent extends BaseEvent {
  event_type: "synthesis_progress";
  progress_percent: number;
  current_action: string;
}

export interface ReportReadyEvent extends BaseEvent {
  event_type: "report_ready";
  report_preview: string;
}

export interface ErrorEvent extends BaseEvent {
  event_type: "error";
  error_code: string;
  error_message: string;
  recoverable: boolean;
}

export interface SessionCancelledEvent extends BaseEvent {
  event_type: "session_cancelled";
  reason: string;
}

export type SSEEvent =
  | PlanDraftEvent
  | PlanUpdatedEvent
  | PhaseChangeEvent
  | AgentStartedEvent
  | AgentProgressEvent
  | AgentCompletedEvent
  | AgentFailedEvent
  | SynthesisStartedEvent
  | SynthesisProgressEvent
  | ReportReadyEvent
  | ErrorEvent
  | SessionCancelledEvent
  | BaseEvent;
