import os
import atexit
import streamlit as st
from dotenv import load_dotenv

from indexer import run_indexing
from qa import ask
from utils import cleanup_temp_data, create_pdf

# ── Setup ──────────────────────────────────────────────────────────────────────

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"
atexit.register(cleanup_temp_data)

st.set_page_config(
    page_title="Legacy Code Archaeologist",
    page_icon="🏛️",
    layout="wide"
)

# ── Session state defaults ─────────────────────────────────────────────────────

if "repo_loaded" not in st.session_state:
    st.session_state.repo_loaded = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "repo_url" not in st.session_state:
    st.session_state.repo_url = ""

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏛️ Git Archaeologist")
    st.markdown("Turn Git history into a searchable knowledge base.")
    st.divider()

    repo_url = st.text_input(
        "GitHub Repo URL",
        value="https://github.com/pallets/flask.git",
        placeholder="https://github.com/owner/repo.git"
    )

    st.markdown("### 🕰️ Excavation Depth")
    depth_option = st.select_slider(
        "How far back should we dig?",
        options=["Recent (100)", "Quarterly (500)", "Yearly (2000)", "Everything (All)"],
        value="Recent (100)"
    )
    limit_map = {
        "Recent (100)": 100,
        "Quarterly (500)": 500,
        "Yearly (2000)": 2000,
        "Everything (All)": 0,
    }
    commit_limit = limit_map[depth_option]

    # API key — env var takes priority, fallback to UI input
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key
        st.markdown(
            "[Get a free Groq API key →](https://console.groq.com/keys)",
            unsafe_allow_html=True
        )

    st.divider()

    if st.button("🔍 Analyze Repo", use_container_width=True):
        if not api_key:
            st.error("Please provide a Groq API key.")
        elif not repo_url.strip():
            st.error("Please enter a repository URL.")
        else:
            with st.spinner("Initializing..."):
                success = run_indexing(repo_url.strip(), commit_limit)
                if success:
                    st.session_state.repo_loaded = True
                    st.session_state.repo_url = repo_url.strip()
                    st.session_state.messages = []

    st.divider()

    # Actions (only show when a repo is loaded)
    if st.session_state.repo_loaded:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        with col2:
            if st.button("↺ Reset", use_container_width=True):
                cleanup_temp_data()
                st.session_state.repo_loaded = False
                st.session_state.messages = []
                st.rerun()

        if st.session_state.messages:
            pdf_bytes = create_pdf(st.session_state.repo_url, st.session_state.messages)
            st.download_button(
                "📄 Download PDF Report",
                data=pdf_bytes,
                file_name="audit_report.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# ── Main chat area ─────────────────────────────────────────────────────────────

st.title("🏛️ Chat with Code History")

if not st.session_state.repo_loaded:
    st.info("👈 Paste a GitHub URL in the sidebar and click **Analyze Repo** to get started.")
    st.stop()

# Render existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new input
if prompt := st.chat_input("Ask anything about the code history..."):
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Stream assistant response
    with st.chat_message("assistant"):
        try:
            # Pass history EXCLUDING the current prompt (qa.py appends it internally)
            history_so_far = st.session_state.messages[:-1]
            stream = ask(prompt, history_so_far)
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            error_msg = f"⚠️ Error: {e}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})