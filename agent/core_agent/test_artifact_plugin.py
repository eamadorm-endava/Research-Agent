import asyncio
import os
import sys

# Add the repository root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts.gcs_artifact_service import GcsArtifactService
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.adk.sessions.session import Session
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.agents.base_agent import BaseAgent
from google.genai import types


class MockAgent(BaseAgent):
    def run(self, ctx):
        pass


async def test_plugin():
    # 1. Setup Mock Services
    bucket_name = "ai_agent_landing_zone"
    artifact_service = GcsArtifactService(bucket_name=bucket_name)
    session_service = InMemorySessionService()

    plugin = SaveFilesAsArtifactsPlugin()

    # 2. Create Mock Context
    session = Session(id="test_session", user_id="test_user", app_name="test_app")
    agent = MockAgent(name="test_agent")

    invocation_context = InvocationContext(
        artifact_service=artifact_service,
        session_service=session_service,
        agent=agent,
        session=session,
        invocation_id="test_invocation",
    )

    # 3. Create Mock Message with Inline Data
    test_data = b"Hello, this is a test artifact content."
    inline_data = types.Blob(
        data=test_data, mime_type="text/plain", display_name="test_file.txt"
    )
    part = types.Part(inline_data=inline_data)
    user_message = types.Content(role="user", parts=[part])

    print(f"Original message parts: {len(user_message.parts)}")

    # 4. Trigger Plugin
    modified_message = await plugin.on_user_message_callback(
        invocation_context=invocation_context, user_message=user_message
    )

    if modified_message:
        print("Plugin modified the message.")
        for part in modified_message.parts:
            if part.text:
                print(f"Text part: {part.text}")
            if part.file_data:
                print(f"File data part: {part.file_data.file_uri}")
    else:
        print("Plugin DID NOT modify the message.")


if __name__ == "__main__":
    asyncio.run(test_plugin())
