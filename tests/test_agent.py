#!/usr/bin/env python3
"""Regression tests for the agent.

Task 1: Test that the agent outputs valid JSON with required fields.
Task 2: Test documentation agent with read_file and list_files tools.
Task 3: Test system agent with query_api tool.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> tuple[dict | None, str | None]:
    """Run the agent and return (parsed_output, error)."""
    project_root = Path(__file__).parent.parent
    result = subprocess.run(
        [sys.executable, "agent.py", question],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
    )

    if result.returncode != 0:
        return None, f"Agent exited with code {result.returncode}: {result.stderr}"

    if not result.stdout.strip():
        return None, "Agent produced no output"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, f"Invalid JSON: {result.stdout[:200]}"

    return data, None


# ---------------------------------------------------------------------------
# Task 1 Tests
# ---------------------------------------------------------------------------

def test_task_1_basic_question() -> None:
    """Test that agent outputs valid JSON with required fields."""
    question = "What is the capital of France?"
    data, error = run_agent(question)

    assert error is None, f"Agent failed: {error}"
    assert data is not None, "No data returned"

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Check field types
    assert isinstance(data["answer"], str), "'answer' should be a string"
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be an array"

    # Check that answer is non-empty
    assert len(data["answer"]) > 0, "'answer' should not be empty"

    print(f"✓ Test passed. Answer: {data['answer'][:100]}")


# ---------------------------------------------------------------------------
# Task 2 Tests (Documentation Agent)
# ---------------------------------------------------------------------------

def test_task_2_merge_conflict_question() -> None:
    """Test documentation agent with a wiki question.

    Question: 'How do you resolve a merge conflict?'
    Expected: read_file in tool_calls, wiki/git-vscode.md in source
    """
    question = "How do you resolve a merge conflict?"
    data, error = run_agent(question)

    assert error is None, f"Agent failed: {error}"
    assert data is not None, "No data returned"

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "source" in data, "Missing 'source' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Check that tools were used
    tool_calls = data.get("tool_calls", [])
    tools_used = [tc.get("tool") for tc in tool_calls]

    assert "read_file" in tools_used, (
        f"Expected 'read_file' in tool calls, got: {tools_used}"
    )

    # Check source contains wiki reference
    source = data.get("source", "")
    assert "wiki/" in source.lower() or any(
        "wiki/" in str(tc.get("args", {})) for tc in tool_calls
    ), f"Expected wiki reference in source, got: {source}"

    print(f"✓ Test passed. Source: {source}")
    print(f"  Tools used: {', '.join(tools_used)}")


def test_task_2_wiki_directory_listing() -> None:
    """Test documentation agent with a directory listing question.

    Question: 'What files are in the wiki?'
    Expected: list_files in tool_calls
    """
    question = "What files are in the wiki?"
    data, error = run_agent(question)

    assert error is None, f"Agent failed: {error}"
    assert data is not None, "No data returned"

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Check that list_files was used
    tool_calls = data.get("tool_calls", [])
    tools_used = [tc.get("tool") for tc in tool_calls]

    assert "list_files" in tools_used, (
        f"Expected 'list_files' in tool calls, got: {tools_used}"
    )

    print(f"✓ Test passed. Tools used: {', '.join(tools_used)}")


# ---------------------------------------------------------------------------
# Task 3 Tests (System Agent)
# ---------------------------------------------------------------------------

def test_task_3_backend_framework_question() -> None:
    """Test system agent with a source code question.

    Question: 'What framework does the backend use?'
    Expected: read_file in tool_calls, answer contains 'FastAPI'
    """
    question = "What framework does the backend use?"
    data, error = run_agent(question)

    assert error is None, f"Agent failed: {error}"
    assert data is not None, "No data returned"

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Check that read_file was used
    tool_calls = data.get("tool_calls", [])
    tools_used = [tc.get("tool") for tc in tool_calls]

    assert "read_file" in tools_used, (
        f"Expected 'read_file' in tool calls, got: {tools_used}"
    )

    # Check answer contains FastAPI
    answer = data.get("answer", "").lower()
    assert "fastapi" in answer, (
        f"Expected 'FastAPI' in answer, got: {data.get('answer', '')}"
    )

    print(f"✓ Test passed. Answer mentions FastAPI")


def test_task_3_database_items_question() -> None:
    """Test system agent with an API query question.

    Question: 'How many items are in the database?'
    Expected: query_api in tool_calls, answer contains a number > 0
    """
    question = "How many items are in the database?"
    data, error = run_agent(question)

    assert error is None, f"Agent failed: {error}"
    assert data is not None, "No data returned"

    # Check required fields
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Check that query_api was used
    tool_calls = data.get("tool_calls", [])
    tools_used = [tc.get("tool") for tc in tool_calls]

    assert "query_api" in tools_used, (
        f"Expected 'query_api' in tool calls, got: {tools_used}"
    )

    # Check answer contains a number
    import re
    answer = data.get("answer", "")
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, f"Expected a number in answer, got: {answer}"

    print(f"✓ Test passed. Answer: {answer[:100]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Task 1 tests...")
    test_task_1_basic_question()

    print("\nRunning Task 2 tests...")
    test_task_2_merge_conflict_question()
    test_task_2_wiki_directory_listing()

    print("\nRunning Task 3 tests...")
    test_task_3_backend_framework_question()
    test_task_3_database_items_question()

    print("\n✓ All tests passed!")
