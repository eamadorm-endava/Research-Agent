import asyncio
import os
import sys

# Ensure local dev execution mode is set for loading configurations in local testing
os.environ["PROD_EXECUTION"] = "False"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import base64
import subprocess
import google.auth
import google.auth.transport.requests
import httpx

# Mock vertexai.Client at module import time to prevent real GCP API initialization for the agent structure
from unittest.mock import patch

with patch("vertexai.Client"):
    from agent.core_agent.agent import research_agent

from google.adk.tools.mcp_tool import McpToolset

PROJECT_ID = "ag-core-ops-auj0"


async def get_gcp_secret(secret_id: str) -> str:
    """Retrieve secret payload from Secret Manager REST API using ADC."""
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    url = f"https://secretmanager.googleapis.com/v1/projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest:access"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise ValueError(
                f"Failed to fetch secret {secret_id}: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        payload_b64 = data["payload"]["data"]
        return base64.b64decode(payload_b64).decode("utf-8").strip()


async def main() -> None:
    print("=====================================================================")
    print("             AGENT-MCP TOOL DISCOVERY INTEGRATION TEST               ")
    print("=====================================================================")

    # Check if port 8085 is already in use
    import socket

    port_in_use = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("127.0.0.1", 8085))
            port_in_use = True
    except ConnectionRefusedError:
        pass

    server_proc = None

    if port_in_use:
        print(
            "\n[INFO] Port 8085 is already in use. Reusing the existing server for testing."
        )
    else:
        print("\n1. Fetching ATLASSIAN_CREDENTIALS from Secret Manager...")
        try:
            credentials_json = await get_gcp_secret("ATLASSIAN_CREDENTIALS")
            print("   Credentials JSON loaded successfully!")
        except Exception as e:
            print(f"   [ERROR] Failed to fetch secret: {e}", file=sys.stderr)
            sys.exit(1)

        # Clean individual env variables to ensure it relies entirely on the JSON secret
        server_env = os.environ.copy()
        for key in [
            "JIRA_USER_EMAIL",
            "JIRA_API_TOKEN",
            "JIRA_INSTANCE_URL",
            "JIRA_CLOUD_ID",
        ]:
            if key in server_env:
                del server_env[key]

        # Inject ATLASSIAN_CREDENTIALS and Landing Zone configuration into the server env
        server_env["ATLASSIAN_CREDENTIALS"] = credentials_json
        server_env["LANDING_ZONE_BUCKET"] = f"{PROJECT_ID}-ai-agent-landing-zone"

        print(
            "\n2. Spawning local Atlassian MCP server on port 8085 (streamable-http)..."
        )
        server_proc = subprocess.Popen(
            [
                "uv",
                "run",
                "--group",
                "mcp_atlassian",
                "python",
                "-m",
                "mcp_servers.atlassian.app.main",
                "--host",
                "127.0.0.1",
                "--port",
                "8085",
                "--transport",
                "streamable-http",
                "--log-level",
                "WARNING",
            ],
            env=server_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for the HTTP server to spin up and bind to the port
        print("   Waiting 4 seconds for server to start...")
        await asyncio.sleep(4.0)

        # Check if the process exited prematurely
        if server_proc.poll() is not None:
            stdout, stderr = server_proc.communicate()
            print(
                f"   [ERROR] MCP Server failed to start. Code: {server_proc.returncode}",
                file=sys.stderr,
            )
            print(f"   Stdout:\n{stdout}", file=sys.stderr)
            print(f"   Stderr:\n{stderr}", file=sys.stderr)
            sys.exit(1)

        print("   Atlassian MCP server process is running.")

    try:
        print("\n3. Resolving Atlassian McpToolset from built research_agent...")
        atlassian_toolset = None
        for tool in research_agent.tools:
            if isinstance(tool, McpToolset) and "8085" in tool._connection_params.url:
                atlassian_toolset = tool
                break

        if not atlassian_toolset:
            print(
                "   [ERROR] Atlassian MCP toolset is not mounted on the research_agent!",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"   Found toolset pointing to: {atlassian_toolset._connection_params.url}"
        )

        print("\n4. Triggering tool discovery on local McpToolset...")
        # McpToolset.get_tools() triggers the /mcp list_tools JSON-RPC call over streamable-http
        discovered_tools = await atlassian_toolset.get_tools()

        print(
            f"\n   Successfully discovered {len(discovered_tools)} tools from MCP server:"
        )
        print("   " + "-" * 60)

        jira_count = 0
        confluence_count = 0

        for idx, tool in enumerate(discovered_tools, 1):
            name = tool.name
            desc = (
                (tool.description[:70] + "...")
                if len(tool.description) > 70
                else tool.description
            )

            # Classify Jira vs Confluence
            if "jira" in name:
                jira_count += 1
                category = "Jira"
            elif "confluence" in name:
                confluence_count += 1
                category = "Confluence"
            else:
                category = "Unknown"

            print(f"   [{idx:02d}] {name:<35} | {category:<10} | {desc}")

        print("   " + "-" * 60)
        print(
            f"   Discovery breakdown: {jira_count} Jira tools, {confluence_count} Confluence tools."
        )

        # Verification asserts
        assert len(discovered_tools) == 18, (
            f"Expected 18 tools, but discovered {len(discovered_tools)}"
        )
        assert jira_count == 6, f"Expected 6 Jira tools, but got {jira_count}"
        assert confluence_count == 12, (
            f"Expected 12 Confluence tools, but got {confluence_count}"
        )

        print(
            "\n[SUCCESS] Integration verification complete. Agent has full access to all 18 tools."
        )

    except Exception as e:
        print(f"\n[ERROR] Integration verification failed: {e}", file=sys.stderr)
        # Dump server logs on failure
        server_proc.terminate()
        stdout, stderr = server_proc.communicate()
        print(f"Server Stderr on failure:\n{stderr}", file=sys.stderr)
        sys.exit(1)
    finally:
        if server_proc:
            print("\n5. Cleaning up local Atlassian MCP server process...")
            server_proc.terminate()
            server_proc.wait()
            print("   MCP server process terminated. Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(main())
