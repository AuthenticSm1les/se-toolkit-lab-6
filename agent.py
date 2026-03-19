#!/usr/bin/env python3
"""CLI agent that calls an LLM and answers questions using tools.

Task 1: Basic LLM calling
Task 2: Added read_file, list_files tools and agentic loop
Task 3: Added query_api tool for backend API access

Usage:
    uv run agent.py "How do you resolve a merge conflict?"

Output (JSON to stdout):
    {
      "answer": "...",
      "source": "wiki/git-vscode.md#resolve-a-merge-conflict",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 10
TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------


def load_env_file(path: str = ".env.agent.secret") -> None:
    """Load environment variables from a .env file."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.resolve()


def validate_path(path: str) -> tuple[bool, str]:
    """Validate that a path is within the project root.

    Returns:
        (is_valid, resolved_path_or_error)
    """
    project_root = get_project_root()

    # Resolve the path (make absolute, resolve ..)
    try:
        resolved = (project_root / path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"

    # Check it's within project root
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return False, f"Path traversal not allowed: {path}"

    return True, str(resolved)


def read_file(path: str) -> str:
    """Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents or error message
    """
    is_valid, result = validate_path(path)
    if not is_valid:
        return f"Error: {result}"

    file_path = Path(result)
    if not file_path.exists():
        return f"Error: File not found: {path}"

    if not file_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return file_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing or error message
    """
    is_valid, result = validate_path(path)
    if not is_valid:
        return f"Error: {result}"

    dir_path = Path(result)
    if not dir_path.exists():
        return f"Error: Directory not found: {path}"

    if not dir_path.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = []
        for entry in sorted(dir_path.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            entries.append(f"{entry.name}{suffix}")
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def query_api(method: str, path: str, body: str | None = None) -> str:
    """Call the backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /items/)
        body: Optional JSON request body

    Returns:
        JSON string with status_code and body
    """
    api_key = os.environ.get("LMS_API_KEY", "")
    base_url = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")

    if not api_key:
        return json.dumps({"error": "LMS_API_KEY not set"})

    url = f"{base_url.rstrip('/')}{path}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, data=body or "{}")
            else:
                return json.dumps({"error": f"Unsupported method: {method}"})

            return json.dumps(
                {
                    "status_code": response.status_code,
                    "body": response.text,
                }
            )
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Tool schemas for LLM
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to read documentation, source code, or configuration files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-vscode.md', 'backend/app/main.py')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to explore the project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app')",
                    }
                },
                "required": ["path"],
            },
        },
    },
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
                        "description": "HTTP method (GET, POST, etc.)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST requests",
                    },
                },
                "required": ["method", "path"],
            },
        },
    },
]

TOOL_MAP = {
    "read_file": read_file,
    "list_files": list_files,
    "query_api": query_api,
}


# ---------------------------------------------------------------------------
# LLM calling
# ---------------------------------------------------------------------------


def call_llm(
    messages: list[dict[str, Any]], timeout: float = TIMEOUT_SECONDS
) -> dict[str, Any]:
    """Call the LLM API and return the response.

    Args:
        messages: List of message dicts with role and content
        timeout: Maximum time to wait for response (seconds)

    Returns:
        dict with 'content' and 'tool_calls' fields

    Raises:
        httpx.HTTPError: If the API request fails
        ValueError: If configuration is missing
    """
    api_key = os.environ.get("LLM_API_KEY", "")
    api_base = os.environ.get("LLM_API_BASE_URL", "")
    model = os.environ.get("LLM_API_MODEL", "coder-model")

    if not api_key:
        raise ValueError("LLM_API_KEY is not set")
    if not api_base:
        raise ValueError("LLM_API_BASE_URL is not set")

    url = f"{api_base.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful assistant that answers questions about a software project.
You have access to tools that read files, list directories, and query the backend API.

When answering:
1. For documentation questions: Use list_files to explore, then read_file to find specific information
2. For system questions: Use query_api to get data from the running backend
3. For source code questions: Use read_file to examine the code
4. Always provide accurate answers with source references
5. Format source as "path/to/file.md#section-anchor" when applicable

IMPORTANT EFFICIENCY RULES:
- When asked to list or explore files in a directory, call list_files ONCE then read the relevant files
- For "list all X" questions: list_files on the directory, then read each file to summarize
- Do NOT call list_files multiple times on the same directory
- Do NOT read files one at a time in a loop - read all needed files and summarize in one answer
- When you have enough information, provide the final answer immediately

Think step by step. If you need to explore first, use list_files. If you need specific information, use read_file or query_api.
Always verify information with tools - don't rely on prior knowledge.
"""


def run_agent(question: str) -> dict[str, Any]:
    """Run the agentic loop and return the result.

    Args:
        question: The user's question

    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    # Initialize message history
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Track all tool calls for output
    all_tool_calls = []

    # Agentic loop
    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1

        # Call LLM
        response = call_llm(messages)
        content = response.get("content") or ""
        tool_calls_raw = response.get("tool_calls") or []

        # If no tool calls, we have the final answer
        if not tool_calls_raw:
            # Extract source from content if possible
            source = ""
            if "wiki/" in content:
                # Try to find a wiki reference
                import re

                match = re.search(r"wiki/[\w\-/]+\.md(?:#[\w\-]+)?", content)
                if match:
                    source = match.group()

            return {
                "answer": content,
                "source": source,
                "tool_calls": all_tool_calls,
            }

        # Execute tool calls
        for tc in tool_calls_raw:
            func_name = tc.get("function", {}).get("name", "")
            args_str = tc.get("function", {}).get("arguments", "{}")

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            # Execute the tool
            tool_func = TOOL_MAP.get(func_name)
            if tool_func:
                try:
                    result = tool_func(**args)
                except Exception as e:
                    result = f"Error: {e}"
            else:
                result = f"Error: Unknown tool: {func_name}"

            # Record the tool call
            all_tool_calls.append(
                {
                    "tool": func_name,
                    "args": args,
                    "result": result,
                }
            )

            # Add tool result to message history
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tc],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tc.get("id", ""),
                }
            )

    # Max iterations reached
    return {
        "answer": "I reached the maximum number of tool calls without finding a complete answer.",
        "source": "",
        "tool_calls": all_tool_calls,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point."""
    # Load environment variables
    load_env_file(".env.agent.secret")

    # Parse CLI arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py <question>", file=sys.stderr)
        return 1

    question = sys.argv[1]

    try:
        # Run the agent
        result = run_agent(question)

        # Output JSON to stdout
        print(json.dumps(result, ensure_ascii=False))
        return 0

    except httpx.HTTPError as e:
        print(f"LLM API error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
