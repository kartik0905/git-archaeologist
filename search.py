import chromadb
from chromadb.utils import embedding_functions

def search_repo(query_text):
    print(f"\n🔎 Searching history for: '{query_text}'...")

    chroma_client = chromadb.PersistentClient(path="./chroma_db")

    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    collection = chroma_client.get_collection(
        name="git_commits",
        embedding_function=sentence_transformer_ef
    )

    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )

    print(f"\n Found {len(results['documents'][0])} relevant historical moments:\n")
    
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        print(f"--- Result {i+1} ---")
        print(f"Date:   {meta['date']}")
        print(f"Author: {meta['author']}")
        print(f"Files:  {meta['files']}")
        print(f"Context: {doc.strip()[:200]}...")
        print("\n")

if __name__ == "__main__":
    while True:
        user_query = input("Ask the Archaeologist (or type 'exit'): ")
        if user_query.lower() == 'exit':
            break
        search_repo(user_query)