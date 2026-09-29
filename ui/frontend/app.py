import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="Research Agent", layout="wide")

API_URL = "http://localhost:8000/api"

st.title("Research Agent 🧠")


st.markdown(
    """
    <style>
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
    
    /* Align User Chat Messages to the right and restrict width */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        flex-direction: row-reverse;
    }
    
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown {
        max-width: 50vw;
        margin-left: auto;
        text-align: right;
    }
    
    /* Hide the user avatar so it looks like WhatsApp/iMessage */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="chatAvatarIcon-user"] {
        display: none !important;
    }
    
    /* Make the st.status expander look subtle and without borders */
    [data-testid="stStatusWidget"] {
        border: none !important;
        background-color: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    
    [data-testid="stStatusWidget"] summary {
        background-color: transparent !important;
        border: none !important;
        color: #888888 !important;
        font-size: 14px !important;
        padding: 0 !important;
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

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("actions") or msg.get("thought_text"):
            with st.status(
                msg.get("status_label", "Ejecutado"), state="complete", expanded=False
            ):
                if msg.get("thought_text"):
                    st.markdown(
                        f"<div style='color: #888888; font-family: sans-serif; font-size: 15px; margin-bottom: 12px; font-style: italic;'>{msg['thought_text']}</div>",
                        unsafe_allow_html=True,
                    )
                if msg.get("actions"):
                    for action in msg["actions"]:
                        st.markdown(action, unsafe_allow_html=True)
        elif msg.get("status_label"):
            st.markdown(
                f"<div style='color: #888888; font-size: 13px; font-family: sans-serif; margin-bottom: 8px;'>{msg['status_label']}</div>",
                unsafe_allow_html=True,
            )

        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Escribe tu consulta...")

# If the user typed something new, capture it and trigger a rerun
if user_input:
    st.session_state.pending_prompt = user_input
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()

# Process the pending prompt (either newly captured or re-attempted after auth)
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt

    with st.chat_message("assistant"):
        status_container = st.empty()
        message_placeholder = st.empty()
        full_response = ""

        # Prepare request
        payload = {"message": prompt, "session_id": st.session_state.session_id}
        headers = {
            # Mocking the IAP header for local development
            "X-Goog-Authenticated-User-Email": "mock-user@example.com"
        }

        try:
            # Initialize status immediately using a context manager so it renders BEFORE blocking
            with status_container.status("Pensando...", expanded=True) as status_box:
                # Stream the SSE response from FastAPI
                response = requests.post(
                    f"{API_URL}/chat/", json=payload, headers=headers, stream=True
                )
                response.raise_for_status()

                auth_required = False
                active_tools = {}
                thought_text = ""
                thought_placeholder = None
                completed_actions = []
                process_start_time = time.time()
                final_label = "Ejecutado"

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
                            # 1. SEQUENTIAL AUTH: Only process the first missing provider
                            provider = missing[0]
                            st.warning(
                                f"Autenticación secuencial requerida. Siguiente paso: Conectar **{provider.title()}**."
                            )

                            login_url = f"{API_URL}/auth/{provider}/login"

                            import streamlit.components.v1 as components

                            components.html(
                                f"""
                                <script>
                                    function openAuth() {{
                                        var authWindow = window.open('{login_url}', 'AuthWindow', 'width=500,height=650,resizable=yes,scrollbars=yes');
                                        var timer = setInterval(function() {{
                                            if (authWindow && authWindow.closed) {{
                                                clearInterval(timer);
                                                // Auto-click the continue button in the parent Streamlit window
                                                var parentDoc = window.parent.document;
                                                var buttons = parentDoc.querySelectorAll('button');
                                                for (var i = 0; i < buttons.length; i++) {{
                                                    if (buttons[i].innerText.includes('Continuar (Autenticación completada)')) {{
                                                        buttons[i].click();
                                                        break;
                                                    }}
                                                }}
                                            }}
                                        }}, 1000);
                                    }}
                                </script>
                                <div style="display: flex; justify-content: left; margin-top: 10px;">
                                    <button onclick="openAuth()" style="background-color: #FF4B4B; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; font-family: sans-serif;">
                                        🔗 Conectar {provider.title()}
                                    </button>
                                </div>
                                """,
                                height=80,
                            )

                            st.info(
                                "💡 Haz clic en el botón para abrir la ventana emergente de autenticación. Al finalizar, la ventana se cerrará sola y el chat continuará automáticamente."
                            )

                            # Fallback button that the JS script will automatically click
                            if st.button("Continuar (Autenticación completada)"):
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
                            if "content" in payload and "parts" in payload["content"]:
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

                                        if thought_placeholder is None and thought_text:
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
                                            duration = time.time() - tool_info["start"]
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
                                "error_message" in payload or "errorMessage" in payload
                            ):
                                err_msg = payload.get("error_message") or payload.get(
                                    "errorMessage"
                                )
                                full_response += f"❌ **Error del Agente**: {err_msg}"
                                message_placeholder.markdown(full_response)

                    # Handle Errors
                    elif event_type == "error":
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

                    final_label = f"Ejecutado en {time_str}"
                    status_box.update(
                        label=final_label, state="complete", expanded=False
                    )
                else:
                    status_box.update(
                        label="Autenticación requerida",
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

        except Exception as e:
            st.error(f"Error conectando con el backend: {e}")
            # Clear the prompt to avoid infinite loop of failures
            st.session_state.pending_prompt = None
