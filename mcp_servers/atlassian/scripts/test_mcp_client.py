import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Resolve the workspace root directory
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


async def main() -> None:
    # Configure parameters to spawn the MCP server as a stdio subprocess
    server_params = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--group",
            "mcp_atlassian",
            "python",
            "-m",
            "mcp_servers.atlassian.app.main",
            "--transport",
            "stdio",
            "--log-level",
            "WARNING",  # Suppress debug/info logs from polluting stdout
        ],
        env=None,
    )

    print("Launching Atlassian MCP server subprocess over stdio...")
    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # 1. Initialize session
                print("Initializing MCP ClientSession...")
                await session.initialize()
                print("Session initialized successfully!")

                # 2. List tools
                print("\nDiscovering available tools:")
                tools_response = await session.list_tools()
                for tool in tools_response.tools:
                    desc = tool.description.splitlines()[0] if tool.description else ""
                    print(f" - [{tool.name}]: {desc}")

                # 3. Call list_jira_projects
                print("\nCalling 'list_jira_projects' tool...")
                projects_result = await session.call_tool(
                    "list_jira_projects", arguments={"request": {}}
                )
                print("Raw Projects Response:")
                print(projects_result.content[0].text)

                # 4. Call search_jira_issues
                print("\nCalling 'search_jira_issues' tool...")
                search_result = await session.call_tool(
                    "search_jira_issues",
                    arguments={
                        "request": {
                            "jql": "updated >= -30d order by created DESC",
                            "max_results": 3,
                        }
                    },
                )
                print("Raw Search Response:")
                print(search_result.content[0].text)

    except Exception as e:
        print(f"\n[ERROR] Test client failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
