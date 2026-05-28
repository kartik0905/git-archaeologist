import os
from openai import OpenAI
from indexer import get_collection

# How many past messages to include for conversation context
HISTORY_WINDOW = 5
# How many commits to retrieve from vector DB per query
TOP_K = 5


def _build_context(query: str) -> str:
    """Retrieve the top-K most relevant commits from ChromaDB."""
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=TOP_K)

    context = ""
    if results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            context += f"--- COMMIT {i + 1} ---\n{doc}\n\n"
    return context


def _build_messages(query: str, context: str, history: list) -> list:
    """
    Construct the full message list for the LLM:
      - system prompt (role + instructions)
      - last N turns of chat history (for multi-turn awareness)
      - current user message with injected commit context
    """
    system_prompt = """You are a Senior Technical Auditor with deep expertise in reading Git history.

You have access to real commit messages and actual code diffs (added/removed lines).

Rules:
- When you see a diff like '- timeout = 5' and '+ timeout = 10', explicitly state the value changed from 5 to 10.
- Always cite the commit hash and author when referencing a specific change.
- If the context doesn't contain enough information to answer, say so clearly — do not hallucinate.
- Keep answers concise and technical. Avoid filler sentences.
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Inject the last N turns of conversation for multi-turn awareness
    recent_history = history[-(HISTORY_WINDOW * 2):]  # each turn = 2 messages
    for msg in recent_history:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Current question with retrieved commit context
    user_message = f"""--- RELEVANT COMMIT HISTORY ---
{context}
--- QUESTION ---
{query}
"""
    messages.append({"role": "user", "content": user_message})
    return messages


def ask(query: str, history: list) -> str:
    """
    Query the RAG pipeline.

    Args:
        query:   The user's current question.
        history: Full chat history so far (list of {role, content} dicts).
                 The current query should NOT be in history yet.

    Returns:
        A generator that streams the assistant's response (for st.write_stream).
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")

    context = _build_context(query)
    messages = _build_messages(query, context, history)

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        stream=True,
    )

    return stream