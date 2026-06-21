# Gemini Enterprise File Ingestion Plugin

This plugin resolves files uploaded via the Gemini Enterprise (GE) UI by securely injecting Google Cloud Storage (GCS) references into the LLM prompt.

## The Architecture of GE File Uploads

When a user interacts with the ADK agent through the Gemini Enterprise chat interface, GE handles file uploads in a very specific, non-standard way:

1. **GCS Persistence First**: GE uses the ADK `ArtifactService` to securely upload the raw file to the agent's Cloud Storage Landing Zone bucket *before* constructing the message prompt. This means IAM conditions and uploader permissions are handled automatically by the ADK framework at upload time.
2. **No Inline Data**: Unlike standard Gemini API calls, GE **never** includes the raw binary file as `inline_data` in the message parts.
3. **Injected Text Tags**: Instead of attaching the file, GE dynamically generates a text tag and injects it directly into the user's prompt text block. The tag follows this exact format:
   ```text
   <start_of_user_uploaded_file: filename>
   <end_of_user_uploaded_file: filename>
   ```

## What This Plugin Does

Without this plugin, the LLM would simply see the text tag (`<start_of_user_uploaded_file: Project_Charter_Aura.pdf>`) but would have absolutely no context or access to the actual underlying file. 

This plugin acts as an interceptor to bridge the gap:
1. **Scans**: It intercepts the incoming `types.Content` message and scans the text parts for the `<start_of_user_uploaded_file...>` tags using Regex.
2. **Discovers**: It extracts the `filename` from the tag and uses `artifact_service.get_artifact_metadata(filename)` to query the Landing Zone bucket and discover the exact `gs://...` URI of the file GE just uploaded.
3. **Replaces**: It slices the text tag out of the prompt and replaces it with a fully hydrated `types.Part(file_data=...)` object. 

When the LLM receives the prompt, the text tag is replaced with a native GCS reference, allowing the agent to securely read the file
