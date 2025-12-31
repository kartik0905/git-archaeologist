import streamlit as st
import os
import shutil
import git
import chromadb
import atexit 
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI
from miner import load_git_history

st.set_page_config(page_title="Legacy Code Archaeologist", page_icon="🏛️", layout="wide")
load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

TEMP_REPO_PATH = "./temp_repo_clone"
CHROMA_PATH = "./chroma_db"

def cleanup_temp_data():
    """Deletes temporary folders to free up space."""
    print("\n🧹 Cleaning up temporary files...")
    if os.path.exists(TEMP_REPO_PATH):
        try:
            shutil.rmtree(TEMP_REPO_PATH)
            print(f"   Deleted {TEMP_REPO_PATH}")
        except Exception as e:
            print(f"   Error deleting repo: {e}")

atexit.register(cleanup_temp_data)

def reset_and_index(repo_url):
    cleanup_temp_data()
    
    status_text = st.empty()
    status_text.info(f"Cloning {repo_url}...")
    try:
        git.Repo.clone_from(repo_url, TEMP_REPO_PATH)
    except Exception as e:
        status_text.error(f"Failed to clone: {e}")
        return False

    status_text.info("⛏️ Mining commit history... (This might take a minute)")
    commits = load_git_history(TEMP_REPO_PATH, limit=200)
    
    if not commits:
        status_text.error("No commits found.")
        return False

    status_text.info(f"Indexing {len(commits)} commits...")
    
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    try:
        chroma_client.delete_collection("git_commits")
    except:
        pass 

    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name="git_commits",
        embedding_function=sentence_transformer_ef
    )

    ids = [c["hash"] for c in commits]
    documents = [c["content"] for c in commits]
    metadatas = [{
        "author": c["author"], 
        "date": c["date"], 
        "files": str(c["files"])
    } for c in commits]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    
    status_text.success(f"Ready! Analyzed {len(commits)} commits from {repo_url}")
    return True

with st.sidebar:
    st.title("🏛️ The Archaeologist")
    st.markdown("Analyze the history of **any** public GitHub repository.")
    
    repo_url = st.text_input("GitHub Repo URL:", value="https://github.com/pallets/flask.git")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("Enter OpenAI API Key:", type="password")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

    if st.button("🔍 Analyze Repo"):
        if not api_key:
            st.error("Please provide an OpenAI API Key.")
        else:
            with st.spinner("Initializing archaeology droids..."):
                if reset_and_index(repo_url):
                    st.session_state["repo_loaded"] = True
                    st.session_state.messages = []

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("Delete Data"):
            cleanup_temp_data()
            st.session_state["repo_loaded"] = False
            st.success("Deleted temp files!")
            st.rerun()

st.title("Chat with Code History")

if not st.session_state.get("repo_loaded"):
    st.info("Enter a GitHub URL and click 'Analyze Repo' to start.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about the history..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            collection = chroma_client.get_collection(
                name="git_commits",
                embedding_function=sentence_transformer_ef
            )
            
            results = collection.query(query_texts=[prompt], n_results=5)
            
            context_text = ""
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    context_text += f"Commit {i+1}:\nAuthor: {meta['author']} | Date: {meta['date']}\nFiles: {meta['files']}\nMessage: {doc}\n\n"

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            full_prompt = f"""
            You are a helpful Software Archaeologist. 
            Based ONLY on the commit history provided below, answer the user's question.
            
            --- COMMIT HISTORY ---
            {context_text}
            
            --- USER QUESTION ---
            {prompt}
            """
            
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": full_prompt}],
                stream=True,
            )
            
            response = st.write_stream(stream)
            st.session_state.messages.append({"role": "assistant", "content": response})
            
        except Exception as e:
            st.error(f"Error: {e}")