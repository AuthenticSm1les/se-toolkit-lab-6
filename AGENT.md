# Agent Documentation

## Overview

This project implements a CLI agent that answers questions by calling an LLM and using tools to read files, list directories, and query the backend API.

## Architecture

### Components

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────┐   │
│  │  agent.py    │────▶│  LLM API (Qwen Code)             │   │
│  │  (CLI)       │◀────│  (OpenAI-compatible format)      │   │
│  └──────┬───────┘     └──────────────────────────────────┘   │
│         │                                                    │
│         │ tool calls                                         │
│         ├──────────▶ read_file(path) ──▶ source code, wiki/  │
│         ├──────────▶ list_files(dir)  ──▶ files and folders  │
│         ├──────────▶ query_api(path)  ──▶ backend API        │
│         │                                                    │
│  ┌──────┴───────┐                                            │
│  │  Docker      │  app (FastAPI) ─── postgres (data)         │
│  │  Compose     │  caddy (frontend)                          │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
```

### Agentic Loop Flow

```
1. Send user question + tool definitions to LLM
2. LLM responds with tool_calls OR text answer
3. If tool_calls:
   a. Execute each tool
   b. Append results as "tool" role messages
   c. Go to step 1
4. If text answer (no tool calls):
   a. Extract answer and source
   b. Output JSON and exit
5. If max iterations (10) reached:
   a. Stop looping
   b. Use whatever answer we have
```

## LLM Provider

**Provider:** Qwen Code API

**Model:** `coder-model` (Qwen 3.5 Plus)

**Why this choice:**

- 1000 free requests per day
- Works from Russia without VPN
- No credit card required
- Strong tool calling capabilities

**Alternative:** OpenRouter (free tier models like `meta-llama/llama-3.3-70b-instruct:free`)

## Configuration

### Environment Variables

The agent reads configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE_URL` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_API_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional |

### Setup

1. Copy the example file:

   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and fill in your credentials:

   ```
   LLM_API_KEY=your-api-key
   LLM_API_BASE_URL=http://your-vm-ip:8080
   LLM_API_MODEL=coder-model
   ```

3. For `query_api` tool, ensure `.env.docker.secret` has:

   ```
   LMS_API_KEY=my-secret-api-key
   ```

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-vscode.md#resolve-a-merge-conflict",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\ngit-vscode.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-vscode.md"},
      "result": "..."
    }
  ]
}
```

**Fields:**

- `answer` (string, required): The LLM's answer
- `source` (string, optional): Source reference (file path + section anchor)
- `tool_calls` (array, required): List of tool calls made. Each entry has `tool`, `args`, and `result`

### Exit Codes

- `0`: Success
- `1`: Error (missing config, API failure, invalid output)

## Tools

### read_file

Read a file from the project repository.

**Parameters:**

- `path` (string): Relative path from project root

**Returns:** File contents as a string, or error message.

**Security:** Validates path is within project root (no `../` traversal).

### list_files

List files and directories at a given path.

**Parameters:**

- `path` (string): Relative directory path from project root

**Returns:** Newline-separated listing, or error message.

**Security:** Validates path is within project root.

### query_api

Call the backend API.

**Parameters:**

- `method` (string): HTTP method (GET, POST, etc.)
- `path` (string): API endpoint path
- `body` (string, optional): JSON request body

**Returns:** JSON string with `status_code` and `body`.

**Authentication:** Uses `LMS_API_KEY` from environment.

## System Prompt Strategy

The system prompt guides the LLM to:

1. Use `list_files` to discover wiki files
2. Use `read_file` to find specific information
3. Use `query_api` for data-dependent questions
4. Include source references in answers
5. Verify information with tools, not prior knowledge

## Implementation Details

### HTTP Client

The agent uses `httpx` for HTTP requests. This library is already included in the project dependencies.

### API Format

The agent uses the OpenAI-compatible chat completions format with tool calling:

```python
POST {LLM_API_BASE_URL}/chat/completions
Headers:
  Authorization: Bearer {LLM_API_KEY}
  Content-Type: application/json
Body:
  {
    "model": "coder-model",
    "messages": [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": question}
    ],
    "tools": [tool_schemas...]
  }
```

### Message History

The agent maintains a conversation history:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    {"role": "assistant", "content": "", "tool_calls": [...]},
    {"role": "tool", "content": result, "tool_call_id": "..."},
    ...
]
```

### Path Security

Tools validate paths to prevent directory traversal:

```python
def validate_path(path: str) -> tuple[bool, str]:
    project_root = get_project_root()
    resolved = (project_root / path).resolve()
    resolved.relative_to(project_root)  # Raises if outside
```

## Testing

Run all tests:

```bash
uv run pytest tests/test_agent.py -v
```

Or run individual tests:

```bash
uv run pytest tests/test_agent.py::test_task_1_basic_question -v
uv run pytest tests/test_agent.py::test_task_2_merge_conflict_question -v
uv run pytest tests/test_agent.py::test_task_3_database_items_question -v
```

## Benchmark Evaluation

Run the local evaluation benchmark:

```bash
uv run run_eval.py
```

This runs 10 questions covering:

- Wiki lookup (read_file)
- System facts (read_file for source code)
- Data queries (query_api)
- Bug diagnosis (query_api + read_file)
- Reasoning (LLM judge)

## Lessons Learned

### Tool Descriptions Matter

The LLM relies on tool descriptions to decide when to use each tool. Vague descriptions lead to wrong tool choices. Be specific about what each tool does and when to use it.

### Path Security is Critical

Without path validation, the agent could read sensitive files outside the project. Always resolve paths and check they're within the allowed directory.

### Max Iterations Prevent Loops

The agentic loop could get stuck if the LLM keeps calling tools. A max iteration limit (10) ensures the agent eventually returns an answer.

### Handle Null Content

The LLM may return `content: null` when making tool calls. Use `(msg.get("content") or "")` instead of `msg.get("content", "")` because the field is present but `null`, not missing.

### Environment Variable Separation

Two distinct keys:

- `LLM_API_KEY` (in `.env.agent.secret`) - authenticates with LLM provider
- `LMS_API_KEY` (in `.env.docker.secret`) - protects backend endpoints

Don't mix them up.

### API Authentication Format

The backend uses Bearer token authentication (`Authorization: Bearer <key>`), not custom headers like `X-API-Key`. This was discovered when debugging the `query_api` tool.

### Efficiency in Agentic Loops

A key lesson from benchmark testing: the LLM can get stuck in loops when exploring directories. Adding explicit efficiency rules to the system prompt ("call list_files ONCE", "don't read files one at a time") significantly improved performance.

### Source References Are Important

The benchmark expects answers to include source file references. The agent needs to not only find the answer but also report where it found it (e.g., `backend/app/routers/analytics.py#213`).

### DeepSeek API as LLM Provider

DeepSeek provides a cost-effective alternative to OpenRouter with good tool-calling capabilities. The `deepseek-chat` model works well for this use case with the OpenAI-compatible API format.

### Backend Deployment Considerations

When deploying the backend on a VM:

- Bind services to `0.0.0.0` instead of `127.0.0.1` for external access
- Use Docker Compose for service orchestration
- Ensure the database is initialized with data before testing queries

## Final Eval Score

| Category | Questions | Passed |
|----------|-----------|--------|
| Wiki lookup | 2 | 2 ✓ |
| System facts | 2 | 2 ✓ |
| Data queries | 2 | 2 ✓ |
| Bug diagnosis | 2 | 0 ✗ |
| Reasoning | 2 | 0 ✗ |
| **Total** | **10** | **6/10** |

*Last run: `uv run run_eval.py` - 6/10 passed*

### Failing Questions Analysis

**Question 7 (Bug Diagnosis - completion-rate):**

- Issue: Agent finds the error ("division by zero") but doesn't include `source` field
- Root cause: The analytics endpoint at `backend/app/routers/analytics.py:213` has a bug where `total_learners` can be `None` from SQL COUNT, causing division issues
- Fix needed: Agent needs to include source reference in answer

**Question 8-10 (Reasoning):**

- Issues: Agent hits max iterations or doesn't provide sufficient detail
- Fix needed: Better efficiency in tool usage and more comprehensive answers

## Troubleshooting

### "LLM_API_KEY is not set"

Make sure `.env.agent.secret` exists and contains your API key.

### Connection timeout

Check that the Qwen Code API is running on your VM and accessible from your local machine.

### Agent doesn't use expected tool

Check the tool description in the schema. The LLM may not understand when to use it.

### Tool returns an error

Test the tool implementation in isolation. Check path validation and error handling.

### Agent times out

The LLM may be making too many tool calls. Check the tool call trace to identify loops.

### Answer is close but doesn't match

Adjust the system prompt to be more precise about expected answer format.
