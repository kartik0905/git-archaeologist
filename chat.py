import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from dotenv import load_dotenv  


load_dotenv()


API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    print("Error: OPENAI_API_KEY not found in .env file.")
    exit(1)

def get_search_results(query_text):
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_collection(
        name="git_commits",
        embedding_function=sentence_transformer_ef
    )

    results = collection.query(query_texts=[query_text], n_results=5)
    
    context_text = ""
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            context_text += f"Commit {i+1}:\n"
            context_text += f"Author: {meta['author']} | Date: {meta['date']}\n"
            context_text += f"Files: {meta['files']}\n"
            context_text += f"Message: {doc}\n\n"
    
    return context_text

def chat_with_repo():
    client = OpenAI(api_key=API_KEY)
    
    print("\nThe Archaeologist is ready (Secure Mode). Ask away!")
    print("   (Type 'exit' to quit)\n")

    while True:
        user_query = input("You: ")
        if user_query.lower() in ['exit', 'quit']:
            break

        print("🔍 Searching history...")
        context = get_search_results(user_query)

        print("🧠 Thinking...")
        prompt = f"""
        You are a helpful Software Archaeologist. 
        Based ONLY on the commit history provided below, answer the user's question.
        If the answer is not in the history, say so.

        --- COMMIT HISTORY ---
        {context}
        
        --- USER QUESTION ---
        {user_query}
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[{"role": "user", "content": prompt}]
            )
            print(f"\nArchaeologist: {response.choices[0].message.content}\n")
            print("-" * 50)
        except Exception as e:
            print(f"Error calling OpenAI: {e}")

if __name__ == "__main__":
    chat_with_repo()