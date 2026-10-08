"""OSIRIS Streamlit chat with same-origin consent and safe text rendering."""

import logging

import streamlit as st
from client import PUBLIC_BASE_URL, chat_events, extract_parts, upload_file

st.set_page_config(page_title="OSIRIS", layout="wide")
logger = logging.getLogger(__name__)

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


def show_connections(providers=("google", "microsoft", "atlassian")):
    """Open provider consent at the IAP-protected public origin."""
    for provider in providers:
        st.link_button(
            f"Connect {provider.title()}",
            f"{PUBLIC_BASE_URL}/api/auth/{provider}/login",
        )


def render_stream(prompt: str, assertion: str | None):
    """Render chat output and preserve an explicit terminal success/error state."""
    placeholder = st.empty()
    answer, actions, completed = "", [], False
    with st.status("Thinking...", expanded=True) as status:
        try:
            for event in chat_events(prompt, st.session_state.session_id, assertion):
                event_type = event.get("type")
                if event_type == "session_info":
                    st.session_state.session_id = event["session_id"]
                elif event_type == "AUTH_REQUIRED":
                    show_connections(event.get("missing_providers", []))
                    st.info("Connect the requested source, then retry your message.")
                    status.update(label="Authentication required", state="error")
                    return
                elif event_type == "agent_event":
                    text, calls = extract_parts(event.get("payload"))
                    answer += text
                    actions.extend(calls)
                    for call in calls:
                        st.write(call)
                    placeholder.markdown(answer + "▌")
                elif event_type == "error":
                    raise RuntimeError(event.get("message", "Agent request failed"))
                elif event_type == "done":
                    completed = True
            if not completed:
                raise RuntimeError(
                    "The response ended before completion. Please retry."
                )
            status.update(label="Completed", state="complete", expanded=False)
            placeholder.markdown(answer)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "actions": actions}
            )
        except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
            logger.warning("Chat request failed")
            status.update(label="Request failed", state="error")
            st.error("The request could not complete. Check your connection and retry.")


def render_upload(assertion: str | None):
    """Attach supported files through a private signed upload, without exposing credentials."""
    uploaded_file = st.file_uploader(
        "Attach a document", type=["pdf", "txt", "md", "csv", "docx"]
    )
    if uploaded_file and st.button("Upload attachment"):
        try:
            st.session_state.attachment = upload_file(uploaded_file, assertion)
            st.success("Attachment uploaded. It will be included in your next message.")
        except Exception:  # noqa: BLE001 - API/UI boundary must not disclose credentials
            st.error("Upload failed. Use a supported file of at most 20 MB and retry.")


st.session_state.setdefault("messages", [])
st.session_state.setdefault("session_id", None)
st.session_state.setdefault("attachment", None)
assertion = st.context.headers.get("X-Goog-IAP-JWT-Assertion")
with st.sidebar:
    st.write("Data sources")
    show_connections()
    st.caption("Connect the sources you need before asking about their content.")
    render_upload(assertion)
    if st.button("New conversation"):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("actions"):
            with st.expander("Tools used"):
                for action in message["actions"]:
                    st.write(action)
        st.markdown(message["content"])

if prompt := st.chat_input("Ask OSIRIS to search your organization's data..."):
    attachment = st.session_state.attachment
    st.session_state.attachment = None
    agent_message = (
        f"{prompt}\nAttached document: {attachment}" if attachment else prompt
    )
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        render_stream(agent_message, assertion)
