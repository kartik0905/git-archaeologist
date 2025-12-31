import chromadb
from chromadb.utils import embedding_functions
from miner import load_git_history
import os

def index_repo():
    print("Setting up Vector Database...")
    

    chroma_client = chromadb.PersistentClient(path="./chroma_db")

    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


    collection = chroma_client.get_or_create_collection(
        name="git_commits",
        embedding_function=sentence_transformer_ef
    )

    repo_path = "./sample_repo"
    commits = load_git_history(repo_path, limit=100)
    
    if not commits:
        print("No commits found. Check your repo path.")
        return

    print(f"Indexing {len(commits)} commits into Vector Store...")


    ids = [c["hash"] for c in commits]
    documents = [c["content"] for c in commits]
    

    metadatas = [{
        "author": c["author"], 
        "date": c["date"], 
        "files": str(c["files"])
    } for c in commits]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    print(f"Success! Indexed {len(commits)} commits.")
    print("   The data is now stored in the './chroma_db' folder.")

if __name__ == "__main__":
    index_repo()