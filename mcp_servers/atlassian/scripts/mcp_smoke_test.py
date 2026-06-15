"""Smoke test script for the Atlassian MCP server."""

import argparse
import json
import urllib.request
from typing import Any, Optional


def post_jsonrpc(endpoint: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Helper to post a JSON-RPC request to the MCP HTTP endpoint.

    Args:
        endpoint: str -> MCP endpoint URL.
        payload: dict[str, Any] -> JSON-RPC payload.

    Returns:
        Optional[dict[str, Any]] -> Response payload, or None.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8").strip()
            if not body:
                return None
            # Extract JSON from Server-Sent Events (SSE) if wrapped
            if body.startswith("event:"):
                data_prefix = "data: "
                for line in body.splitlines():
                    if line.startswith(data_prefix):
                        body = line[len(data_prefix) :].strip()
                        break
            return json.loads(body)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        try:
            print(e.read().decode("utf-8"))
        except Exception:
            pass
        raise


def main() -> None:
    """Entry point for the smoke test."""
    parser = argparse.ArgumentParser(
        description="Smoke test the Atlassian MCP streamable-http endpoint."
    )
    parser.add_argument(
        "--endpoint", default="http://localhost:8085/mcp", help="MCP endpoint URL"
    )
    args = parser.parse_args()

    print(f"Connecting to MCP endpoint: {args.endpoint}")

    # 1. Initialize
    init_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "atlassian-local-smoke-client",
                    "version": "0.1.0",
                },
            },
        },
    )
    print("initialize ->", json.dumps(init_response, indent=2))

    # 2. Initialized Notification
    initialized_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )
    if initialized_response:
        print(
            "notifications/initialized ->", json.dumps(initialized_response, indent=2)
        )

    # 3. List Tools
    tools_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    print("tools/list ->", json.dumps(tools_response, indent=2))

    # 4. List Projects
    print("\nCalling list_jira_projects...")
    list_projects_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_jira_projects",
                "arguments": {
                    "request": {},
                },
            },
        },
    )
    print(
        "tools/call(list_jira_projects) ->",
        json.dumps(list_projects_response, indent=2),
    )

    # 5. Search Issues JQL
    jql_query = "updated >= -30d order by created DESC"
    print(f"\nCalling search_jira_issues with JQL: '{jql_query}'...")
    search_issues_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search_jira_issues",
                "arguments": {
                    "request": {
                        "jql": jql_query,
                        "max_results": 5,
                    }
                },
            },
        },
    )
    print(
        "tools/call(search_jira_issues) ->",
        json.dumps(search_issues_response, indent=2),
    )


if __name__ == "__main__":
    main()
