import streamlit as st
import os
import shutil
import git
import chromadb
import atexit
import time
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI
from miner import load_git_history
from fpdf import FPDF

st.set_page_config(page_title="Legacy Code Archaeologist", page_icon="🏛️", layout="wide")
load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

TEMP_REPO_PATH = "./temp_repo_clone"
CHROMA_PATH = "./chroma_db"

def cleanup_temp_data():
    if os.path.exists(TEMP_REPO_PATH):
        try: shutil.rmtree(TEMP_REPO_PATH)
        except: pass
    if os.path.exists(CHROMA_PATH):
        try: shutil.rmtree(CHROMA_PATH)
        except: pass

atexit.register(cleanup_temp_data)

def create_pdf(repo_url, messages):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Legacy Code Archaeologist - Audit Report", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 10, f"Repository: {repo_url}", ln=True, align="C")
    pdf.cell(200, 10, f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)
    
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Archaeologist"
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, f"{role}:", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.set_text_color(0, 0, 0)
        clean_content = msg["content"].encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, clean_content)
        pdf.ln(5)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
    return pdf.output(dest="S").encode("latin-1")

def reset_and_index(repo_url, commit_limit):
    cleanup_temp_data()
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    if commit_limit == 0:
        status_text.info(f"⏳ Cloning {repo_url} (FULL HISTORY)... This may take a while.")
        try:
            git.Repo.clone_from(repo_url, TEMP_REPO_PATH)
        except Exception as e:
            status_text.error(f"Failed to clone: {e}")
            return False
    else:
        status_text.info(f"⏳ Shallow cloning {repo_url} (Last {commit_limit} commits)...")
        try:
            git.Repo.clone_from(repo_url, TEMP_REPO_PATH, depth=commit_limit)
        except Exception as e:
            status_text.error(f"Failed to clone: {e}")
            return False

    status_text.info("⛏️ Mining & Indexing in batches...")
    
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    try: chroma_client.delete_collection("git_commits")
    except: pass 
    
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name="git_commits",
        embedding_function=sentence_transformer_ef
    )

    BATCH_SIZE = 10
    current_batch_ids = []
    current_batch_docs = []
    current_batch_meta = []
    
    total_processed = 0
    
    for commit in load_git_history(TEMP_REPO_PATH):
        current_batch_ids.append(commit["hash"])
        current_batch_docs.append(commit["content"])
        current_batch_meta.append({"author": commit["author"], "date": commit["date"]})
        
        if len(current_batch_ids) >= BATCH_SIZE:
            collection.add(
                ids=current_batch_ids, 
                documents=current_batch_docs, 
                metadatas=current_batch_meta
            )
            total_processed += len(current_batch_ids)
            status_text.info(f"🧠 Indexed {total_processed} commits...")
        
            display_limit = commit_limit if commit_limit > 0 else 2000
            progress_bar.progress(min(total_processed / display_limit, 1.0))
            
            current_batch_ids = []
            current_batch_docs = []
            current_batch_meta = []

    if current_batch_ids:
        collection.add(
            ids=current_batch_ids, 
            documents=current_batch_docs, 
            metadatas=current_batch_meta
        )
        total_processed += len(current_batch_ids)

    progress_bar.empty()
    status_text.success(f"✅ Ready! Analyzed {total_processed} commits.")
    return True

with st.sidebar:
    st.title("🏛️ Archaeologist Scale")
    st.markdown("Optimized for **Big Repos**.")
    repo_url = st.text_input("GitHub Repo URL:", value="https://github.com/pallets/flask.git")
    
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
        "Everything (All)": 0
    }
    commit_limit = limit_map[depth_option]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("Enter OpenAI API Key:", type="password")
        if api_key: os.environ["OPENAI_API_KEY"] = api_key

    if st.button("🔍 Analyze Repo"):
        if not api_key: st.error("Need API Key.")
        else:
            with st.spinner("Initializing..."):
                if reset_and_index(repo_url, commit_limit):
                    st.session_state["repo_loaded"] = True
                    st.session_state.messages = []

    st.divider()

    if "messages" in st.session_state and st.session_state.messages:
        pdf_bytes = create_pdf(repo_url, st.session_state.messages)
        st.download_button("📄 Download PDF Report", pdf_bytes, "audit_report.pdf", "application/pdf")

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("🗑️ Reset"):
            cleanup_temp_data()
            st.session_state["repo_loaded"] = False
            st.rerun()

st.title("Chat with Code History")

if not st.session_state.get("repo_loaded"):
    st.info("👈 Enter a GitHub URL to start.")
    st.stop()

if "messages" not in st.session_state: st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about code changes..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

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
            results = collection.query(query_texts=[prompt], n_results=3)
            
            context_text = ""
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    context_text += f"--- COMMIT {i+1} ---\n{doc}\n\n"

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            full_prompt = f"""
            You are a Senior Technical Auditor. 
            You have access to the COMMIT MESSAGES and the ACTUAL CODE DIFFS.
            
            Use the 'Code Changes' section in the history to answer specific questions about what code was modified.
            If you see a diff like '- timeout = 5' and '+ timeout = 10', explicitly mention that the value changed from 5 to 10.
            
            --- HISTORY DATA ---
            {context_text}
            
            --- QUESTION ---
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