import git
import chromadb
import streamlit as st
from chromadb.utils import embedding_functions

from miner import load_git_history
from utils import cleanup_temp_data, TEMP_REPO_PATH, CHROMA_PATH, inject_github_token

BATCH_SIZE = 10
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _get_embedding_function():
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )


def get_collection():
    """Return the existing ChromaDB collection (call after indexing)."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_collection(
        name="git_commits",
        embedding_function=_get_embedding_function()
    )


def _clone_repo(repo_url: str, commit_limit: int, token: str, status_text) -> bool:
    """Clone repo — shallow if limit set, full otherwise."""
    
    auth_url = inject_github_token(repo_url, token)
    
    try:
        if commit_limit == 0:
            status_text.info(f"⏳ Cloning full history of {repo_url}... this may take a while.")
            git.Repo.clone_from(auth_url, TEMP_REPO_PATH)
        else:
            status_text.info(f"⏳ Shallow cloning {repo_url} (last {commit_limit} commits)...")
            git.Repo.clone_from(auth_url, TEMP_REPO_PATH, depth=commit_limit)
        return True
    except Exception as e:
        status_text.error(f"❌ Failed to clone: {e}")
        return False


def _validate_repo(repo_url: str, token: str, status_text) -> bool:
    """Check that the URL points to a real, accessible repo."""
    if not repo_url.startswith(("http://", "https://")):
        status_text.error("❌ Invalid URL. Must start with http:// or https://")
        return False

    status_text.info("📡 Verifying repository...")
    
    auth_url = inject_github_token(repo_url, token)
    
    try:
        git.cmd.Git().ls_remote(auth_url)
        return True
    except git.exc.GitCommandError as e:
        msg = str(e).lower()
        if "not found" in msg:
            status_text.error("❌ Repository not found. Check the URL.")
        elif "authentication" in msg or "could not read password" in msg:
            status_text.error("🔒 Repository is private. Access denied.")
        else:
            status_text.error(f"❌ Git error: {e}")
        return False


def _index_commits(commit_limit: int, status_text, progress_bar) -> int:
    """Mine commits from cloned repo and insert into ChromaDB. Returns total indexed."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)


    try:
        client.delete_collection("git_commits")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name="git_commits",
        embedding_function=_get_embedding_function()
    )

    batch_ids, batch_docs, batch_meta = [], [], []
    total = 0
    display_limit = commit_limit if commit_limit > 0 else 2000

    for commit in load_git_history(TEMP_REPO_PATH):
        batch_ids.append(commit["hash"])
        batch_docs.append(commit["content"])
        batch_meta.append({"author": commit["author"], "date": commit["date"],"timestamp": commit["timestamp"]})

        if len(batch_ids) >= BATCH_SIZE:
            collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)
            total += len(batch_ids)
            status_text.info(f"🧠 Indexed {total} commits...")
            progress_bar.progress(min(total / display_limit, 1.0))
            batch_ids, batch_docs, batch_meta = [], [], []


    if batch_ids:
        collection.add(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)
        total += len(batch_ids)

    return total



def run_indexing(repo_url: str, commit_limit: int, token: str = None) -> bool:
    """
    Full pipeline: validate → cleanup → clone → index.
    Returns True on success. Renders its own Streamlit progress UI.
    """
    cleanup_temp_data()

    status_text = st.empty()
    progress_bar = st.progress(0)

    if not _validate_repo(repo_url, token, status_text):
        return False

    if not _clone_repo(repo_url, commit_limit, token, status_text):
        return False

    status_text.info("⛏️ Mining & indexing commits...")
    total = _index_commits(commit_limit, status_text, progress_bar)

    progress_bar.empty()
    status_text.success(f"✅ Ready! Indexed {total} commits.")
    return True