# Task 3 Plan: The System Agent

## Overview

This task extends the documentation agent from Task 2 with a new tool (`query_api`) that can query the backend API. This enables the agent to answer two new kinds of questions:

1. **Static system facts** — framework, ports, status codes (read source code)
2. **Data-dependent queries** — item count, scores, analytics (query the running backend)

## query_api Tool Schema

**Purpose:** Call the backend API to query data or check system status.

**Parameters:**

- `method` (string, required): HTTP method (GET, POST, etc.)
- `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST requests

**Returns:** JSON string with `status_code` and `body`.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` via the `X-API-Key` header.

**Schema:**

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Call the backend API to query data or check system status. Use this for questions about the running system.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, etc.)"
        },
        "path": {
          "type": "string",
          "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "Optional JSON request body for POST requests"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

## Implementation Steps

### 1. Add query_api tool function

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API."""
    api_key = os.environ.get("LMS_API_KEY", "")
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
    
    if not api_key:
        return json.dumps({"error": "LMS_API_KEY not set"})
    
    url = f"{base_url.rstrip('/')}{path}"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    
    # Use httpx to make the request
    # Return JSON with status_code and body
```

### 2. Register tool in TOOL_MAP

Add `query_api` to the `TOOLS` list and `TOOL_MAP` dictionary alongside `read_file` and `list_files`.

### 3. Update system prompt

Update the system prompt to guide the LLM on when to use each tool:

- `list_files` / `read_file` — for documentation and source code questions
- `query_api` — for data-dependent questions about the running system

### 4. Environment variables

Ensure the agent reads all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE_URL` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_API_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional |

> **Important:** The autochecker runs the agent with different credentials. Never hardcode these values.

## System Prompt Strategy

The updated system prompt should guide the LLM to:

1. For documentation questions: Use `list_files` to explore, then `read_file` to find specific information
2. For source code questions: Use `read_file` to examine the code
3. For system/data questions: Use `query_api` to get data from the running backend
4. Always provide accurate answers with source references
5. Verify information with tools — don't rely on prior knowledge

## Testing Strategy

Add 2 regression tests:

1. **Backend framework question:** "What framework does the backend use?"
   - Expected: `read_file` in tool_calls
   - Expected answer contains "FastAPI"

2. **Database items question:** "How many items are in the database?"
   - Expected: `query_api` in tool_calls
   - Expected answer contains a number > 0

## Benchmark Evaluation Plan

After implementing `query_api`, run the benchmark:

```bash
uv run run_eval.py
```

## Initial Benchmark Score

| Category | Questions | Passed |
|----------|-----------|--------|
| Wiki lookup | 2 | 2 ✓ |
| System facts | 2 | 2 ✓ |
| Data queries | 2 | 2 ✓ |
| Bug diagnosis | 2 | 0 ✗ |
| Reasoning | 2 | 0 ✗ |
| **Total** | **10** | **6/10** |

### Failing Questions Analysis

**Question 7 (Bug Diagnosis - completion-rate):**

- Issue: Agent finds the error ("division by zero") but doesn't include `source` field
- Root cause: The analytics endpoint at `backend/app/routers/analytics.py:213` has `total_learners` potentially being `None` from SQL COUNT
- Fix needed: Agent needs to include source reference in answer

**Question 8-10 (Reasoning):**

- Issues: Agent hits max iterations or doesn't provide sufficient detail
- Fix needed: Better efficiency in tool usage and more comprehensive answers

## Iteration Strategy

1. ✓ Run `run_eval.py` to get initial score (6/10)
2. ✓ Improved system prompt with efficiency rules
3. ✓ Fixed `query_api` to use Bearer token auth
4. ⏳ Add source field extraction for bug diagnosis questions
5. ⏳ Increase max iterations for complex reasoning questions
6. ⏳ Re-run and verify improvements

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Agent doesn't call `query_api` for data questions | Tool description too vague | Clarify when to use `query_api` in system prompt |
| `query_api` returns 401 | Missing `LMS_API_KEY` | Ensure `.env.docker.secret` has the key |
| Agent times out | Too many tool calls | Reduce max iterations or optimize tool descriptions |
| Answer doesn't match expected keywords | Phrasing issue | Adjust system prompt to be more precise |

## Initial Benchmark Score

*To be filled after first run:*

| Category | Questions | Passed |
|----------|-----------|--------|
| Wiki lookup | 2 | - |
| System facts | 2 | - |
| Data queries | 2 | - |
| Bug diagnosis | 2 | - |
| Reasoning | 2 | - |
| **Total** | **10** | **- |

## Iteration Strategy

1. Run `run_eval.py` to get initial score
2. For each failing question:
   - Examine the tool call trace
   - Identify why the wrong tool was chosen or wrong answer given
   - Fix tool descriptions or system prompt
   - Re-run and verify
3. Repeat until all 10 questions pass
4. Document lessons learned in `AGENT.md`

## Success Criteria

- `query_api` tool authenticates correctly with `LMS_API_KEY`
- Agent answers static system questions correctly (framework, ports, status codes)
- Agent answers data-dependent questions with plausible values
- `run_eval.py` passes all 10 local questions
- Tests pass consistently
