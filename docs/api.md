# API Reference

Deep Research provides a REST API with SSE streaming for real-time updates.

**Base URL**: `http://localhost:12050`

## Research Endpoints

### Start Research Session

Start a new research session with the given query.

```http
POST /api/research/start
Content-Type: application/json
```

**Request Body**:

```json
{
  "query": "Your research question",
  "language": "en"  // optional, auto-detected if omitted
}
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-1234-5678-9abc-def012345678",
  "phase": "planning",
  "user_query": "Your research question",
  "detected_language": "en",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

### Get Session Status

Retrieve current status of a research session.

```http
GET /api/research/{session_id}
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "phase": "researching",
  "user_query": "Your research question",
  "detected_language": "en",
  "plan": {
    "understanding": "User wants to understand...",
    "plan_items": [
      {
        "id": "p1",
        "topic": "Topic 1",
        "description": "Description...",
        "status": "completed"
      },
      {
        "id": "p2",
        "topic": "Topic 2",
        "description": "Description...",
        "status": "in_progress"
      }
    ],
    "estimated_time_minutes": 15
  },
  "agent_progress": [
    {
      "agent_id": "researcher-p1",
      "plan_item_id": "p1",
      "topic": "Topic 1",
      "status": "completed",
      "progress_percent": 100
    },
    {
      "agent_id": "researcher-p2",
      "plan_item_id": "p2",
      "topic": "Topic 2",
      "status": "running",
      "progress_percent": 45,
      "current_action": "Searching for recent studies..."
    }
  ],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:35:00Z"
}
```

**Response** `404 Not Found`:

```json
{
  "detail": "Session not found"
}
```

---

### Confirm Research Plan

Confirm or modify the generated research plan.

```http
POST /api/research/{session_id}/confirm
Content-Type: application/json
```

**Request Body**:

```json
{
  "action": "confirm",  // "confirm" | "skip" | "modify"
  "skip_items": ["p3", "p4"],  // optional, item IDs to skip
  "modifications": [...]  // optional, modified plan items
}
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "phase": "researching",
  "message": "Plan confirmed, starting research phase"
}
```

---

### Provide Clarification Answers

Submit answers to clarification questions from the planner.

```http
POST /api/research/{session_id}/clarify
Content-Type: application/json
```

**Request Body**:

```json
{
  "answers": [
    {
      "question": "Are you interested in specific agent types?",
      "answer": "Focus on multi-agent orchestration patterns"
    }
  ]
}
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "phase": "planning",
  "message": "Clarifications received, refining plan"
}
```

---

### Cancel Session

Cancel an in-progress research session.

```http
POST /api/research/{session_id}/cancel
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "phase": "cancelled",
  "message": "Research session cancelled"
}
```

---

### Resume Session

Resume a previously interrupted session from checkpoint.

```http
POST /api/research/{session_id}/resume
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "phase": "researching",
  "message": "Session resumed from checkpoint",
  "checkpoint_time": "2025-01-15T10:32:00Z"
}
```

**Response** `404 Not Found`:

```json
{
  "detail": "No checkpoint found for session"
}
```

---

### Get Final Report

Retrieve the final research report (only available after synthesis completes).

```http
GET /api/research/{session_id}/report
```

**Response** `200 OK`:

```json
{
  "session_id": "64e11013-...",
  "report": "# Research Report\n\n## Executive Summary\n...",
  "format": "markdown",
  "generated_at": "2025-01-15T10:45:00Z"
}
```

**Response** `400 Bad Request` (if not completed):

```json
{
  "detail": "Report not yet available. Current phase: researching"
}
```

---

## SSE Event Stream

Subscribe to real-time events for a research session.

```http
GET /api/research/{session_id}/stream
Accept: text/event-stream
```

### Event Types

#### phase_change

Emitted when the workflow transitions between phases.

```
event: phase_change
data: {
  "session_id": "64e11013-...",
  "old_phase": "planning",
  "new_phase": "plan_review",
  "timestamp": "2025-01-15T10:31:00Z"
}
```

Phases: `planning` → `plan_review` → `researching` → `synthesizing` → `completed`

#### plan_draft

Emitted when a research plan is generated.

```
event: plan_draft
data: {
  "session_id": "64e11013-...",
  "plan": {
    "understanding": "...",
    "plan_items": [...],
    "estimated_time_minutes": 15
  }
}
```

#### plan_progress

Emitted during planning phase to show progress.

```
event: plan_progress
data: {
  "session_id": "64e11013-...",
  "current_action": "Analyzing research scope..."
}
```

#### agent_started

Emitted when a researcher agent begins execution.

```
event: agent_started
data: {
  "session_id": "64e11013-...",
  "agent_id": "researcher-p1",
  "plan_item_id": "p1",
  "topic": "Multi-agent architectures"
}
```

#### agent_progress

Emitted periodically with agent progress updates.

```
event: agent_progress
data: {
  "session_id": "64e11013-...",
  "progress": {
    "agent_id": "researcher-p1",
    "plan_item_id": "p1",
    "topic": "Multi-agent architectures",
    "status": "running",
    "progress_percent": 65,
    "current_action": "WebSearch 'orchestrator patterns 2025'"
  }
}
```

#### agent_completed

Emitted when a researcher agent finishes.

```
event: agent_completed
data: {
  "session_id": "64e11013-...",
  "result": {
    "agent_id": "researcher-p1",
    "plan_item_id": "p1",
    "topic": "Multi-agent architectures",
    "findings": "Key findings summary...",
    "sources": [
      {"title": "Source 1", "url": "https://..."}
    ],
    "confidence": 0.85,
    "execution_time": 45.2
  }
}
```

#### agent_failed

Emitted when a researcher agent encounters an error.

```
event: agent_failed
data: {
  "session_id": "64e11013-...",
  "agent_id": "researcher-p2",
  "error": "Timeout after 600 seconds"
}
```

#### synthesis_started

Emitted when synthesis phase begins.

```
event: synthesis_started
data: {
  "session_id": "64e11013-...",
  "total_results": 4
}
```

#### synthesis_progress

Emitted during report generation.

```
event: synthesis_progress
data: {
  "session_id": "64e11013-...",
  "progress_percent": 50,
  "current_action": "Generating report..."
}
```

#### report_ready

Emitted when the final report is ready.

```
event: report_ready
data: {
  "session_id": "64e11013-...",
  "report_preview": "# Research Report\n\n## Executive Summary..."
}
```

#### checkpoint_saved

Emitted when a checkpoint is saved.

```
event: checkpoint_saved
data: {
  "session_id": "64e11013-...",
  "timestamp": "2025-01-15T10:33:00Z"
}
```

#### error

Emitted on errors.

```
event: error
data: {
  "session_id": "64e11013-...",
  "error_code": "PLANNING_FAILED",
  "error_message": "Failed to parse planner response"
}
```

---

## Configuration Endpoints

### Get Configuration

Retrieve current system configuration.

```http
GET /api/config
```

**Response** `200 OK`:

```json
{
  "api_host": "0.0.0.0",
  "api_port": 12050,
  "agent_provider": "codex_cli",
  "planner_provider": null,
  "researcher_provider": null,
  "synthesizer_provider": null,
  "planner_model": "gpt-5.2",
  "researcher_model": "gpt-5.2",
  "synthesizer_model": "gpt-5.2",
  "max_parallel_agents": 10,
  "agent_timeout_seconds": 600,
  "checkpoint_interval_seconds": 60,
  "log_level": "INFO"
}
```

---

### Update Configuration

Update system configuration (runtime changes).

```http
PUT /api/config
Content-Type: application/json
```

**Request Body** (partial updates supported):

```json
{
  "max_parallel_agents": 5,
  "researcher_model": "gpt-5.2",
  "researcher_provider": "codex_cli"
}
```

**Response** `200 OK`:

```json
{
  "api_host": "0.0.0.0",
  "api_port": 12050,
  "agent_provider": "codex_cli",
  "planner_provider": null,
  "researcher_provider": "codex_cli",
  "synthesizer_provider": null,
  "planner_model": "gpt-5.2",
  "researcher_model": "gpt-5.2",
  "synthesizer_model": "gpt-5.2",
  "max_parallel_agents": 5,
  "agent_timeout_seconds": 600,
  "checkpoint_interval_seconds": 60,
  "log_level": "INFO"
}
```

---

## Health Endpoints

### Health Check

Basic health check endpoint.

```http
GET /health
```

**Response** `200 OK`:

```json
{
  "status": "ok"
}
```

---

### Readiness Check

Check if the service is ready to accept requests.

```http
GET /ready
```

**Response** `200 OK`:

```json
{
  "status": "ready",
  "database": "connected",
  "agent_provider": "opencode",
  "provider_status": "available"
}
```

**Response** `503 Service Unavailable`:

```json
{
  "status": "not_ready",
  "database": "connected",
  "agent_provider": "opencode",
  "provider_status": "unavailable",
  "error": "OpenCode server not responding"
}
```

---

## Error Responses

All endpoints may return these error responses:

### 400 Bad Request

```json
{
  "detail": "Invalid request body"
}
```

### 404 Not Found

```json
{
  "detail": "Session not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error",
  "error_code": "INTERNAL_ERROR"
}
```

---

## Client Examples

### Python (httpx)

```python
import httpx
import asyncio

async def run_research():
    async with httpx.AsyncClient(base_url="http://localhost:12050") as client:
        # Start session
        resp = await client.post("/api/research/start", json={
            "query": "Research AI agent trends"
        })
        session_id = resp.json()["session_id"]

        # Wait for plan
        await asyncio.sleep(5)

        # Confirm plan
        await client.post(f"/api/research/{session_id}/confirm", json={
            "action": "confirm"
        })

        # Poll for completion
        while True:
            resp = await client.get(f"/api/research/{session_id}")
            if resp.json()["phase"] == "completed":
                break
            await asyncio.sleep(5)

        # Get report
        resp = await client.get(f"/api/research/{session_id}/report")
        print(resp.json()["report"])

asyncio.run(run_research())
```

### JavaScript (fetch + SSE)

```javascript
// Start research
const resp = await fetch('http://localhost:12050/api/research/start', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: 'Research AI agent trends' })
});
const { session_id } = await resp.json();

// Subscribe to events
const eventSource = new EventSource(
  `http://localhost:12050/api/research/${session_id}/stream`
);

eventSource.addEventListener('agent_progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Agent ${data.progress.agent_id}: ${data.progress.progress_percent}%`);
});

eventSource.addEventListener('report_ready', (e) => {
  const data = JSON.parse(e.data);
  console.log('Report ready:', data.report_preview);
  eventSource.close();
});
```

### cURL

```bash
# Start session
SESSION=$(curl -s -X POST http://localhost:12050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"query": "Research AI trends"}' | jq -r '.session_id')

# Stream events
curl -N http://localhost:12050/api/research/$SESSION/stream

# Get report (after completion)
curl http://localhost:12050/api/research/$SESSION/report | jq -r '.report'
```
