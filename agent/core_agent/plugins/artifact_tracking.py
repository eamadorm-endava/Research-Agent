from __future__ import annotations

from typing import Optional

from google.genai import types
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin

_ARTIFACT_STATE_KEY = "latest_uploaded_artifacts"


class ArtifactTrackingSaveFilesPlugin(SaveFilesAsArtifactsPlugin):
    """Saves uploaded files as artifacts and tracks the latest artifact names in session state."""

    async def on_user_message_callback(
        self,
        *,
        invocation_context,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        processed_message = await super().on_user_message_callback(
            invocation_context=invocation_context,
            user_message=user_message,
        )

        tracked_names: list[str] = []
        pending_delta = invocation_context.session.state.get(
            self.name + ":pending_delta"
        )
        if isinstance(pending_delta, dict):
            tracked_names.extend(
                str(name)
                for name in pending_delta.keys()
                if name is not None and str(name).strip()
            )

        if not tracked_names and user_message.parts:
            for part in user_message.parts:
                inline_data = getattr(part, "inline_data", None)
                display_name = getattr(inline_data, "display_name", None)
                if display_name:
                    tracked_names.append(str(display_name))

        if tracked_names:
            state = invocation_context.session.state
            existing_names = state.get(_ARTIFACT_STATE_KEY) or []
            deduped_names: list[str] = []
            for name in [*existing_names, *tracked_names]:
                if name not in deduped_names:
                    deduped_names.append(name)
            state[_ARTIFACT_STATE_KEY] = deduped_names

        return processed_message
