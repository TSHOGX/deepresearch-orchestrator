/**
 * API client for the Deep Research backend.
 */

import type {
  StartResearchRequest,
  ConfirmPlanRequest,
  ResearchSessionResponse,
  SessionListResponse,
  ConfigResponse,
  ConfigUpdateRequest,
} from "@/types";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown
  ) {
    super(`API Error: ${status} ${statusText}`);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    throw new ApiError(response.status, response.statusText, body);
  }
  return response.json();
}

/**
 * Health check endpoints
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
  const response = await fetch(`${API_BASE.replace("/api", "")}/health`);
  return handleResponse(response);
}

export async function checkReady(): Promise<{ ready: boolean }> {
  const response = await fetch(`${API_BASE.replace("/api", "")}/ready`);
  return handleResponse(response);
}

/**
 * Research endpoints
 */
export async function startResearch(
  request: StartResearchRequest
): Promise<ResearchSessionResponse> {
  const response = await fetch(`${API_BASE}/research/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse(response);
}

export async function getSession(
  sessionId: string
): Promise<ResearchSessionResponse> {
  const response = await fetch(`${API_BASE}/research/${sessionId}`);
  return handleResponse(response);
}

export async function listSessions(
  limit: number = 10
): Promise<SessionListResponse> {
  const response = await fetch(`${API_BASE}/research?limit=${limit}`);
  return handleResponse(response);
}

export async function confirmPlan(
  sessionId: string,
  request: ConfirmPlanRequest
): Promise<ResearchSessionResponse> {
  const response = await fetch(`${API_BASE}/research/${sessionId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse(response);
}

export async function cancelSession(
  sessionId: string
): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE}/research/${sessionId}/cancel`, {
    method: "POST",
  });
  return handleResponse(response);
}

export async function resumeSession(
  sessionId: string
): Promise<ResearchSessionResponse> {
  const response = await fetch(`${API_BASE}/research/${sessionId}/resume`, {
    method: "POST",
  });
  return handleResponse(response);
}

export async function getReport(
  sessionId: string,
  format: "markdown" | "html" = "markdown"
): Promise<{ report: string; format: string }> {
  const response = await fetch(
    `${API_BASE}/research/${sessionId}/report?format=${format}`
  );
  return handleResponse(response);
}

/**
 * Config endpoints
 */
export async function getConfig(): Promise<ConfigResponse> {
  const response = await fetch(`${API_BASE}/config`);
  return handleResponse(response);
}

export async function updateConfig(
  request: ConfigUpdateRequest
): Promise<ConfigResponse> {
  const response = await fetch(`${API_BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse(response);
}

/**
 * SSE streaming - returns the event source URL
 */
export function getStreamUrl(sessionId: string): string {
  return `${API_BASE}/research/${sessionId}/stream`;
}

export { ApiError };
