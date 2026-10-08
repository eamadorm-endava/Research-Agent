import streamlit as st
import requests
import json
import time
import os
from ui.frontend.authentication import render_authentication, request_headers

st.set_page_config(page_title="OSIRIS", layout="wide")

API_URL = os.getenv("API_URL", "http://localhost:8000/api")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://osiris.endava.app").rstrip("/")


st.markdown(
    """
    <div style="text-align: center; margin-bottom: 3rem; margin-top: 1rem;">
        <div style="font-size: 5rem; font-weight: 300; letter-spacing: -0.15rem; margin-bottom: 0.5rem; line-height: 1; transform: scale(1, 0.85); display: inline-block;">OSIRIS</div>
        <p style="font-size: 1.2rem; font-weight: 400; color: #888888; max-width: 800px; margin: 0 auto; line-height: 1.5;">A hierarchical multi-agent system designed to break information silos<br>and search across enterprise data sources</p>
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600&display=swap');

    /* Performant font application that doesn't override Streamlit's native icons or cause layout thrashing */
    html, body, .stApp, .stMarkdown, p, h1, h2, h3, h4, h5, h6, button, input, textarea {
        font-family: 'Montserrat', sans-serif !important;
    }

    @keyframes spin {
        100% { transform: rotate(360deg); }
    }
    .spin-icon {
        animation: spin 1s linear infinite;
    }
    
    /* Remove background and borders from ALL chat messages */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    
    /* Remove focus outlines globally for chat messages and status widgets to prevent pink borders */
    [data-testid="stChatMessage"]:focus,
    [data-testid="stChatMessage"]:active,
    [data-testid="stChatMessage"]:focus-visible,
    [data-testid="stChatMessage"]:focus-within,
    [data-testid="stStatusWidget"]:focus,
    [data-testid="stStatusWidget"]:active,
    [data-testid="stStatusWidget"]:focus-visible,
    [data-testid="stStatusWidget"]:focus-within {
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    

    /* Hide avatars completely */
    [data-testid="stChatMessage"] > div:first-child {
        display: none !important;
    }
    
    /* Align User Chat Messages to the right */
    [data-testid="stChatMessage"]:has(.user-msg) {
        flex-direction: row-reverse;
    }
    
    /* Container styling for user messages */
    [data-testid="stChatMessage"]:has(.user-msg) .stMarkdown {
        background-color: #2b2d31 !important; /* Dark container background */
        color: #ffffff !important;
        border-radius: 18px 18px 0px 18px !important;
        padding: 12px 18px !important;
        max-width: fit-content !important;
        margin-left: auto !important;
        margin-right: 0 !important;
        text-align: left; /* Keep text left aligned inside the container */
        box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    }
    
    /* Ensure the parent takes full width to allow auto margins to work */
    [data-testid="stChatMessage"]:has(.user-msg) [data-testid="stChatMessageContent"] {
        width: 100% !important;
        display: flex !important;
        justify-content: flex-end !important;
    }

    /* Redesign Chat Input Bar */
    [data-testid="stChatFloatingInputContainer"] {
        background: transparent !important;
        padding-bottom: 2rem !important;
    }
    [data-testid="stChatInput"] {
        max-width: 1000px !important;
        margin: 0 auto !important;
        border-radius: 40px !important;
        border: 1px solid #333 !important; /* This is our outer border */
        background-color: #1e1e1e !important;
        padding: 0 !important;
    }
    
    /* Remove native inner borders/backgrounds of Streamlit's input wrapper */
    [data-testid="stChatInput"] > div {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    
    /* Ensure the textarea doesn't get a focus outline that looks like a second border */
    [data-testid="stChatInput"] textarea {
        border-radius: 40px !important;
        background-color: transparent !important;
        color: #ffffff !important;
        padding-left: 24px !important;
        padding-right: 24px !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        outline: none !important;
        box-shadow: none !important;
    }
    
    [data-testid="stChatInput"] button {
        background-color: transparent !important;
        border: none !important;
    }
    
    /* Make chat placeholder gray */
    [data-testid="stChatInput"] textarea::placeholder {
        color: #888888 !important;
    }
    
    /* Aggressively remove all backgrounds and borders from st.status and expanders, without killing the spinner */
    [data-testid="stStatusWidget"],
    [data-testid="stExpander"],
    [data-testid="stStatusWidget"] > div,
    [data-testid="stExpander"] > div,
    [data-testid="stStatusWidget"] details,
    [data-testid="stExpander"] details,
    [data-testid="stStatusWidget"] summary,
    [data-testid="stExpander"] summary {
        background-color: transparent !important;
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Hide native browser arrow in details summary that overlaps with Streamlit's SVG arrow */
    [data-testid="stStatusWidget"] summary,
    [data-testid="stExpander"] summary {
        list-style: none !important;
    }
    
    /* Disable hover background on summary */
    [data-testid="stStatusWidget"] summary:hover,
    [data-testid="stExpander"] summary:hover,
    [data-testid="stStatusWidget"] summary:focus,
    [data-testid="stExpander"] summary:focus {
        background-color: transparent !important;
        background: none !important;
        color: inherit !important;
    }
    [data-testid="stStatusWidget"] summary::-webkit-details-marker,
    [data-testid="stExpander"] summary::-webkit-details-marker {
        display: none !important;
    }

    [data-testid="stStatusWidget"] [data-testid="stExpanderDetails"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_agent_action(icon_svg, text):
    return f"""
    <div style="color: #888888; font-family: sans-serif; font-size: 15px; margin-bottom: 4px; display: flex; align-items: center;">
        {icon_svg}
        <span style="margin-left: 8px;">{text}</span>
    </div>
    """


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "required_connections" not in st.session_state:
    st.session_state.required_connections = []

# Display chat history
for msg in st.session_state.messages:
    is_user = msg["role"] == "user"
    avatar = "👤" if is_user else "🔘"

    with st.chat_message(msg["role"], avatar=avatar):
        if msg.get("status_label"):
            with st.status(msg["status_label"], state="complete", expanded=False):
                if msg.get("thought_text"):
                    st.markdown(
                        f"<div style='color: #888888; font-family: sans-serif; font-size: 15px; margin-bottom: 12px; font-style: italic;'>{msg['thought_text']}</div>",
                        unsafe_allow_html=True,
                    )
                if msg.get("actions"):
                    for action in msg["actions"]:
                        st.markdown(action, unsafe_allow_html=True)

                # If there are no actions or thoughts, the status box will just be empty and collapsed,
                # maintaining the same visual checkmark and padding as the others.

        # Merge the user-msg tag into the single markdown output to avoid empty bubbles
        content = (
            f"<span class='user-msg'></span>{msg['content']}"
            if is_user
            else msg["content"]
        )
        st.markdown(content, unsafe_allow_html=True)

# Chat input
user_input = st.chat_input(
    "Ask OSIRIS to search your organization's data...",
    disabled=bool(st.session_state.required_connections),
)

# If the user typed something new, capture it and trigger a rerun
if user_input:
    st.session_state.pending_prompt = user_input
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()

if st.session_state.pending_prompt and st.session_state.required_connections:
    with st.chat_message("assistant", avatar="🔘"):
        render_authentication(API_URL, PUBLIC_BASE_URL)
    st.stop()

# Process the pending prompt (either newly captured or re-attempted after auth)
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt

    with st.chat_message("assistant", avatar="🔘"):
        status_container = st.empty()
        message_placeholder = st.empty()
        full_response = ""

        # Prepare request
        payload = {"message": prompt, "session_id": st.session_state.session_id}

        # Forward the signed user assertion separately from the Cloud Run ID token.
        headers = request_headers(API_URL)

        status_box = None
        try:
            # Initialize status immediately using a context manager so it renders BEFORE blocking
            with status_container.status("Thinking...", expanded=True) as status_box:
                # Force Streamlit to flush the UI (render the user message and the status box)
                # before we block the thread with the synchronous requests.post call.
                import time

                time.sleep(0.05)

                # Stream the SSE response from FastAPI
                with requests.post(
                    f"{API_URL}/chat/", json=payload, headers=headers, stream=True
                ) as response:
                    response.raise_for_status()

                    auth_required = False
                    stream_failed = False
                    active_tools = {}
                    thought_text = ""
                    thought_placeholder = None
                    completed_actions = []
                    process_start_time = time.time()
                    final_label = "Executed"

                    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                        if not line or not line.startswith("data: "):
                            continue

                        # Parse the JSON payload from the SSE stream
                        raw_data = line[6:]
                        event_data = json.loads(raw_data)

                        event_type = event_data.get("type")
                        # DEBUG: uncomment if needed
                        # st.write(f"Received event: {event_type}")

                        # Handle Authentication Requirement
                        if event_type == "AUTH_REQUIRED":
                            auth_required = True
                            missing = event_data.get("missing_providers", [])

                            if missing:
                                st.session_state.required_connections = missing
                                st.rerun()

                            break

                        # Handle Session Tracking
                        elif event_type == "session_info":
                            st.session_state.session_id = event_data.get("session_id")

                        # Handle Agent Output
                        elif event_type == "agent_event":
                            payload = event_data.get("payload", {})
                            # print(f"DEBUG FRONTEND PAYLOAD: {payload}")

                            if isinstance(payload, str):
                                # Sometimes ADK yields just the string directly
                                full_response += payload
                                message_placeholder.markdown(full_response + "▌")
                            # Basic ADK Event Parser
                            elif isinstance(payload, dict):
                                if (
                                    "content" in payload
                                    and "parts" in payload["content"]
                                ):
                                    for part in payload["content"]["parts"]:
                                        # 1. Text Chunks
                                        if "text" in part:
                                            full_response += part["text"]
                                            message_placeholder.markdown(
                                                full_response + "▌"
                                            )

                                        # 2. Tool Calls
                                        elif (
                                            "functionCall" in part
                                            or "function_call" in part
                                        ):
                                            # Route any pending text to the thoughts panel
                                            if full_response.strip():
                                                thought_text += full_response + "\\n\\n"
                                                full_response = ""
                                                message_placeholder.empty()

                                            if (
                                                thought_placeholder is None
                                                and thought_text
                                            ):
                                                thought_placeholder = (
                                                    status_box.container().empty()
                                                )
                                            if thought_placeholder and thought_text:
                                                thought_placeholder.markdown(
                                                    f"<div style='color: #888888; font-family: sans-serif; font-size: 15px; margin-bottom: 12px; font-style: italic;'>{thought_text}</div>",
                                                    unsafe_allow_html=True,
                                                )

                                            call_data = part.get(
                                                "functionCall"
                                            ) or part.get("function_call")
                                            call_id = call_data.get("id")
                                            func_name = call_data.get("name", "unknown")
                                            func_args = call_data.get("args", {})

                                            # Format Name (e.g., transfer_to_agent -> Transfer To Agent)
                                            clean_name = (
                                                func_name.replace("_", " ")
                                                .replace("-", " ")
                                                .title()
                                            )

                                            svg_transfer = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>'
                                            svg_skill = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>'
                                            svg_tool = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>'

                                            if func_name == "transfer_to_agent":
                                                target = func_args.get(
                                                    "agent_name"
                                                ) or func_args.get(
                                                    "subagent_name", "unknown"
                                                )
                                                clean_target = (
                                                    target.replace("_", " ")
                                                    .replace("-", " ")
                                                    .title()
                                                )
                                                action_html = format_agent_action(
                                                    svg_transfer,
                                                    f"Transfer To Subagent {clean_target}",
                                                )
                                                status_box.markdown(
                                                    action_html, unsafe_allow_html=True
                                                )
                                                completed_actions.append(action_html)
                                            else:
                                                ph = status_box.container().empty()
                                                start_time = time.time()

                                                is_skill = (
                                                    "skill" in str(func_args).lower()
                                                    or func_name == "load_skill"
                                                )
                                                if is_skill:
                                                    skill_name = func_args.get(
                                                        "skill_name", func_name
                                                    )
                                                    clean_skill = (
                                                        skill_name.replace("_", " ")
                                                        .replace("-", " ")
                                                        .title()
                                                    )

                                                    svg_spinner = '<svg class="spin-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>'

                                                    ph.markdown(
                                                        format_agent_action(
                                                            svg_skill,
                                                            f"Reading Skill {clean_skill} - {svg_spinner}",
                                                        ),
                                                        unsafe_allow_html=True,
                                                    )
                                                    active_tools[call_id] = {
                                                        "ph": ph,
                                                        "start": start_time,
                                                        "type": "skill",
                                                        "name": clean_skill,
                                                        "svg": svg_skill,
                                                    }
                                                else:
                                                    svg_spinner = '<svg class="spin-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#888888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>'
                                                    ph.markdown(
                                                        format_agent_action(
                                                            svg_tool,
                                                            f"{clean_name} - {svg_spinner}",
                                                        ),
                                                        unsafe_allow_html=True,
                                                    )
                                                    active_tools[call_id] = {
                                                        "ph": ph,
                                                        "start": start_time,
                                                        "type": "function",
                                                        "name": clean_name,
                                                        "svg": svg_tool,
                                                    }

                                        # 3. Tool Responses
                                        elif (
                                            "functionResponse" in part
                                            or "function_response" in part
                                        ):
                                            resp_data = part.get(
                                                "functionResponse"
                                            ) or part.get("function_response")
                                            call_id = resp_data.get("id")
                                            if call_id in active_tools:
                                                tool_info = active_tools[call_id]
                                                duration = (
                                                    time.time() - tool_info["start"]
                                                )
                                                ph = tool_info["ph"]

                                                if tool_info["type"] == "skill":
                                                    action_html = format_agent_action(
                                                        tool_info["svg"],
                                                        f"Reading Skill {tool_info['name']} - {duration:.1f}s",
                                                    )
                                                else:
                                                    action_html = format_agent_action(
                                                        tool_info["svg"],
                                                        f"{tool_info['name']} - {duration:.1f}s",
                                                    )
                                                ph.markdown(
                                                    action_html, unsafe_allow_html=True
                                                )
                                                completed_actions.append(action_html)

                                                del active_tools[call_id]

                                elif (
                                    "error_message" in payload
                                    or "errorMessage" in payload
                                ):
                                    err_msg = payload.get(
                                        "error_message"
                                    ) or payload.get("errorMessage")
                                    stream_failed = True
                                    full_response += f"❌ **Agent Error**: {err_msg}"
                                    message_placeholder.markdown(full_response)

                        # Handle Errors
                        elif event_type == "error":
                            stream_failed = True
                            st.error(event_data.get("message"))

                    # Update status block before context manager exits (if no auth required)
                    if not auth_required:
                        total_duration = time.time() - process_start_time
                        mins = int(total_duration // 60)
                        secs = int(total_duration % 60)
                        if mins > 0:
                            time_str = f"{mins} min {secs} s"
                        else:
                            time_str = f"{secs} s"

                        final_label = f"Executed in {time_str}"
                        if stream_failed:
                            final_label = "Request failed"
                        status_box.update(
                            label=final_label,
                            state="error" if stream_failed else "complete",
                            expanded=False,
                        )
                    else:
                        status_box.update(
                            label="Authentication required",
                            state="complete",
                            expanded=False,
                        )

                # If we successfully completed the loop without requiring auth
                if not auth_required:
                    st.session_state.pending_prompt = None  # Clear the prompt
                    if full_response:
                        message_placeholder.markdown(full_response)
                        msg_data = {"role": "assistant", "content": full_response}
                        msg_data["status_label"] = final_label
                        if completed_actions or thought_text:
                            msg_data["actions"] = completed_actions
                            msg_data["thought_text"] = thought_text
                        st.session_state.messages.append(msg_data)
                    st.rerun()

        except Exception as e:
            if status_box is not None:
                status_box.update(label="Request failed", state="error")
            if (
                isinstance(e, requests.HTTPError)
                and e.response is not None
                and e.response.status_code == 401
            ):
                st.error(
                    "Your access session could not be verified. Reload this page and try again."
                )
            else:
                st.error(f"Error connecting to the backend: {e}")
            # Clear the prompt to avoid infinite loop of failures
            st.session_state.pending_prompt = None
