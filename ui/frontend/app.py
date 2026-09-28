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

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Escribe tu consulta..."):
    # Append and show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Placeholder for assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # We use a container specifically for the tool accordions
        status_container = st.container()

        # Prepare request
        payload = {"message": prompt, "session_id": st.session_state.session_id}
        headers = {
            # Mocking the IAP header for local development
            "X-Goog-Authenticated-User-Email": "dev-user@example.com"
        }

        try:
            # Stream the SSE response from FastAPI
            response = requests.post(
                f"{API_URL}/chat/", json=payload, headers=headers, stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue

                # Parse the JSON payload from the SSE stream
                raw_data = line[6:]
                event_data = json.loads(raw_data)

                event_type = event_data.get("type")

                # Handle Authentication Requirement
                if event_type == "AUTH_REQUIRED":
                    missing = event_data.get("missing_providers", [])
                    st.warning("Autenticación requerida para continuar:")

                    cols = st.columns(len(missing))
                    for i, provider in enumerate(missing):
                        with cols[i]:
                            # Render the specific login button
                            login_url = f"{API_URL}/auth/{provider}/login"
                            st.link_button(f"Conectar {provider.title()}", login_url)
                    break

                # Handle Session Tracking
                elif event_type == "session_info":
                    st.session_state.session_id = event_data.get("session_id")

                # Handle Agent Output
                elif event_type == "agent_event":
                    payload = event_data.get("payload", {})

                    # Basic ADK Event Parser
                    if "content" in payload and "parts" in payload["content"]:
                        for part in payload["content"]["parts"]:
                            # 1. Text Chunks
                            if "text" in part:
                                full_response += part["text"]
                                message_placeholder.markdown(full_response + "▌")

                            # 2. Tool Calls
                            elif "functionCall" in part:
                                func_name = part["functionCall"]["name"]
                                func_args = part["functionCall"].get("args", {})

                                # Render the accordion (spinner is built into st.status while it runs)
                                with status_container.status(
                                    f"Ejecutando {func_name}...", expanded=False
                                ) as status:
                                    st.write("Argumentos:")
                                    st.json(func_args)
                                    status.update(
                                        label=f"Completado: {func_name}",
                                        state="complete",
                                    )

                # Handle Errors
                elif event_type == "error":
                    st.error(event_data.get("message"))

            # Clean up the typing cursor
            if full_response:
                message_placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )

        except Exception as e:
            st.error(f"Error conectando con el backend: {e}")
