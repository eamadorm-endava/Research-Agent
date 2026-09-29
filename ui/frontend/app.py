import streamlit as st
import requests
import json

st.set_page_config(page_title="Research Agent", layout="wide")

API_URL = "http://localhost:8000/api"

st.title("Research Agent 🧠")

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
        status_container = st.container()
        message_placeholder = st.empty()
        full_response = ""

        # Prepare request
        payload = {"message": prompt, "session_id": st.session_state.session_id}
        headers = {
            # Mocking the IAP header for local development
            "X-Goog-Authenticated-User-Email": "mock-user@example.com"
        }

        try:
            # Stream the SSE response from FastAPI
            response = requests.post(
                f"{API_URL}/chat/", json=payload, headers=headers, stream=True
            )
            response.raise_for_status()

            auth_required = False

            # Show a thinking indicator while waiting for the stream
            message_placeholder.markdown("⏳ *Pensando...*")

            status_box = None

            for line in response.iter_lines(decode_unicode=True):
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
                        # Handle agent transfers
                        if (
                            "actions" in payload
                            and "transfer_to_agent" in payload["actions"]
                        ):
                            if status_box is None:
                                status_box = status_container.status(
                                    "🧠 Pensamientos del agente...", expanded=False
                                )
                            target = payload["actions"]["transfer_to_agent"]
                            status_box.markdown(
                                f"🤖 **Cambiando de agente:** Transfiriendo a `{target}`"
                            )

                        if "content" in payload and "parts" in payload["content"]:
                            for part in payload["content"]["parts"]:
                                # 1. Text Chunks
                                if "text" in part:
                                    full_response += part["text"]
                                    message_placeholder.markdown(full_response + "▌")

                                # 2. Tool Calls
                                elif "functionCall" in part or "function_call" in part:
                                    if status_box is None:
                                        status_box = status_container.status(
                                            "🧠 Pensamientos del agente...",
                                            expanded=False,
                                        )

                                    call_data = part.get("functionCall") or part.get(
                                        "function_call"
                                    )
                                    func_name = call_data.get("name", "unknown")
                                    func_args = call_data.get("args", {})

                                    if (
                                        "skill" in str(func_args).lower()
                                        or func_name == "view_file"
                                    ):
                                        status_box.markdown(
                                            f"📖 **Consultando conocimiento**: `{func_name}`"
                                        )
                                    else:
                                        status_box.markdown(
                                            f"🛠️ **Ejecutando herramienta**: `{func_name}`"
                                        )

                                    with status_box:
                                        st.json(func_args)

                        elif "error_message" in payload or "errorMessage" in payload:
                            err_msg = payload.get("error_message") or payload.get(
                                "errorMessage"
                            )
                            full_response += f"❌ **Error del Agente**: {err_msg}"
                            message_placeholder.markdown(full_response)

                # Handle Errors
                elif event_type == "error":
                    st.error(event_data.get("message"))

            # Update status block if it was created
            if status_box is not None:
                status_box.update(label="✅ Proceso completado", state="complete")

            # If we successfully completed the loop without requiring auth
            if not auth_required:
                st.session_state.pending_prompt = None  # Clear the prompt
                if full_response:
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": full_response}
                    )

        except Exception as e:
            st.error(f"Error conectando con el backend: {e}")
            # Clear the prompt to avoid infinite loop of failures
            st.session_state.pending_prompt = None
