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
        try:
            shutil.rmtree(TEMP_REPO_PATH)
        except: pass
    if os.path.exists(CHROMA_PATH):
        try:
            shutil.rmtree(CHROMA_PATH)
        except: pass

atexit.register(cleanup_temp_data)

def reset_and_index(repo_url):
    cleanup_temp_data()
    status_text = st.empty()
    status_text.info(f"⏳ Cloning {repo_url}...")
    try:
        git.Repo.clone_from(repo_url, TEMP_REPO_PATH)
    except Exception as e:
        status_text.error(f"Failed to clone: {e}")
        return False

    status_text.info("⛏️ Mining commits & diffs... (This might take a minute)")
    commits = load_git_history(TEMP_REPO_PATH, limit=50)
    
    if not commits:
        status_text.error("No commits found.")
        return False

    status_text.info(f"🧠 Indexing {len(commits)} commits...")
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

    ids = [c["hash"] for c in commits]
    documents = [c["content"] for c in commits]
    metadatas = [{"author": c["author"], "date": c["date"]} for c in commits]

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    status_text.success(f"✅ Ready! Analyzed {len(commits)} commits.")
    return True

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

with st.sidebar:
    st.title("🏛️ Archaeologist Pro")
    st.markdown("Now with **Code Diff Analysis**.")
    repo_url = st.text_input("GitHub Repo URL:", value="https://github.com/pallets/flask.git")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("Enter OpenAI API Key:", type="password")
        if api_key: os.environ["OPENAI_API_KEY"] = api_key

    if st.button("🔍 Analyze Repo"):
        if not api_key: st.error("Need API Key.")
        else:
            with st.spinner("Analyzing code changes..."):
                if reset_and_index(repo_url):
                    st.session_state["repo_loaded"] = True
                    st.session_state.messages = []

    st.divider()

    if "messages" in st.session_state and st.session_state.messages:
        pdf_bytes = create_pdf(repo_url, st.session_state.messages)

        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name="audit_report.pdf",
            mime="application/pdf"
        )

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