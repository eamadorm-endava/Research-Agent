import argparse
import json
import urllib.request
from typing import Any, Dict, Optional


def post_jsonrpc(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8").strip()
        if not body:
            return None
        return json.loads(body)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test a local MCP streamable-http endpoint."
    )
    parser.add_argument("--endpoint", default="http://localhost:8080/mcp")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    init_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gcs-local-smoke-client", "version": "0.1.0"},
            },
        },
    )
    print("initialize ->", json.dumps(init_response, indent=2))

    initialized_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
    )
    if initialized_response:
        print("notifications/initialized ->", json.dumps(initialized_response, indent=2))

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

    list_objects_response = post_jsonrpc(
        args.endpoint,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_objects",
                "arguments": {
                    "request": {
                        "bucket_name": args.bucket,
                        "prefix": args.prefix,
                    }
                },
            },
        },
    )
    print("tools/call(list_objects) ->", json.dumps(list_objects_response, indent=2))


if __name__ == "__main__":
    main()
