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
if "author_filter" not in st.session_state:
    st.session_state.author_filter = ""
if "start_date" not in st.session_state:
    st.session_state.start_date = None
if "end_date" not in st.session_state:
    st.session_state.end_date = None

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏛️ Git Archaeologist")
    st.markdown("Turn Git history into a searchable knowledge base.")
    st.divider()

    st.markdown("### 🔌 Repository Connection")
    repo_url = st.text_input(
        "GitHub Repo URL",
        value="https://github.com/pallets/flask.git",
        placeholder="https://github.com/owner/repo.git"
    )

    github_token = st.text_input(
        "GitHub PAT (Private Repos)",
        type="password",
        help="Optional. Required for private repositories (needs 'repo' scope). \n\n🔒 **Security Note:** Your token is never saved to disk. It is strictly held in memory during the cloning process, and all temporary repository files are aggressively wiped from the server when you click Reset or close the app."
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
                success = run_indexing(repo_url.strip(), commit_limit, token=github_token)
                if success:
                    st.session_state.repo_loaded = True
                    st.session_state.repo_url = repo_url.strip()
                    st.session_state.messages = []

    st.divider()

    if st.session_state.get("repo_loaded", False):

        st.markdown("### 🎯 Search Filters")
        st.caption("Narrow the search scope — leave blank to search all commits.")

        author_filter = st.text_input(
            "Filter by Author",
            value=st.session_state.author_filter,
            placeholder="e.g., Armin Ronacher",
            help="Exact match on the Git commit author name."
        )
        st.session_state.author_filter = author_filter

        date_filter = st.date_input(
            "Filter by Date Range",
            value=(),
            help="Select a start and end date to narrow commits."
        )

        if len(date_filter) == 2:
            st.session_state.start_date = date_filter[0].strftime("%Y-%m-%d")
            st.session_state.end_date = date_filter[1].strftime("%Y-%m-%d")
        else:
            st.session_state.start_date = None
            st.session_state.end_date = None

        # Show active filter badge so the user knows filters are on
        active = []
        if st.session_state.author_filter:
            active.append(f"👤 `{st.session_state.author_filter}`")
        if st.session_state.start_date and st.session_state.end_date:
            active.append(f"📅 `{st.session_state.start_date}` → `{st.session_state.end_date}`")
        if active:
            st.success("Active filters: " + "  ·  ".join(active))

        st.divider()

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
                st.session_state.author_filter = ""
                st.session_state.start_date = None
                st.session_state.end_date = None
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

# Warn user when filters are active
if st.session_state.get("repo_loaded"):
    active_warnings = []
    if st.session_state.author_filter:
        active_warnings.append(f"👤 Author: `{st.session_state.author_filter}`")
    if st.session_state.start_date and st.session_state.end_date:
        active_warnings.append(f"📅 Date: `{st.session_state.start_date}` → `{st.session_state.end_date}`")
    if active_warnings:
        st.warning("⚠️ Active filters: " + "  ·  ".join(active_warnings) + " — results are scoped. Clear them in the sidebar for full history.")

if not st.session_state.repo_loaded:
    st.info("👈 Paste a GitHub URL in the sidebar and click **Analyze Repo** to get started.")
    st.stop()

# Render existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle new input
if prompt := st.chat_input("Ask anything about the code history..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            history_so_far = st.session_state.messages[:-1]
            stream = ask(
                prompt,
                history_so_far,
                author=st.session_state.author_filter or None,
                start_date=st.session_state.start_date,
                end_date=st.session_state.end_date,
            )
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response})
        except Exception as e:
            error_msg = f"⚠️ Error: {e}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})