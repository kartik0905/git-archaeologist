import os
from openai import OpenAI
from indexer import get_collection

# How many past messages to include for conversation context
HISTORY_WINDOW = 5
# How many commits to fetch from ChromaDB before reranking
RETRIEVAL_K = 10
# How many to pass to the LLM after reranking
RERANK_TOP_N = 3

# Lazy-loaded reranker — None until first query
_reranker = None


def _get_reranker():
    """
    Lazy-load the cross-encoder reranker on first use.
    Downloads ~85MB on first call, then cached by sentence-transformers.
    """
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def _rerank(query: str, docs: list[str]) -> list[str]:
    """
    Score each (query, doc) pair with the cross-encoder.
    Returns docs sorted by relevance score, top RERANK_TOP_N only.
    """
    if not docs:
        return docs

    reranker = _get_reranker()
    pairs = [(query, doc) for doc in docs]
    scores = reranker.predict(pairs)

    # Sort by score descending, keep top N
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:RERANK_TOP_N]]


def _build_where_clause(author: str = None, start_date: str = None, end_date: str = None) -> dict | None:
    """
    Build a ChromaDB `where` clause from optional filters.
    Returns None if no filters are active.
    """
    conditions = []

    if author and author.strip():
        conditions.append({"author": {"$eq": author.strip()}})

    if start_date:
        conditions.append({"date": {"$gte": start_date}})

    if end_date:
        conditions.append({"date": {"$lte": end_date + " 23:59:59"}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _build_context(
    query: str,
    author: str = None,
    start_date: str = None,
    end_date: str = None,
) -> tuple[str, bool]:
    """
    Retrieve top-K commits from ChromaDB, rerank, return top-N as context string.
    """
    collection = get_collection()
    where = _build_where_clause(author, start_date, end_date)
    filters_active = where is not None

    try:
        if where:
            results = collection.query(
                query_texts=[query],
                n_results=RETRIEVAL_K,
                where=where
            )
        else:
            results = collection.query(query_texts=[query], n_results=RETRIEVAL_K)
    except Exception:
        results = collection.query(query_texts=[query], n_results=RETRIEVAL_K)
        filters_active = False

    docs = results["documents"][0] if results["documents"] else []

    # Rerank — narrows RETRIEVAL_K → RERANK_TOP_N
    reranked_docs = _rerank(query, docs)

    context = ""
    for i, doc in enumerate(reranked_docs):
        context += f"--- COMMIT {i + 1} ---\n{doc}\n\n"

    return context, filters_active


def _build_messages(
    query: str,
    context: str,
    history: list,
    author: str = None,
    start_date: str = None,
    end_date: str = None,
    filters_active: bool = False,
) -> list:
    """Construct the full message list for the LLM."""
    filter_lines = []
    if filters_active:
        if author:
            filter_lines.append(f"- Author filter: '{author}' (exact match)")
        if start_date and end_date:
            filter_lines.append(f"- Date filter: {start_date} → {end_date}")
        elif start_date:
            filter_lines.append(f"- Date filter: from {start_date} onwards")
        elif end_date:
            filter_lines.append(f"- Date filter: up to {end_date}")

    filter_note = ""
    if filter_lines:
        filter_note = "\n\nActive search filters (commits below already match these):\n" + "\n".join(filter_lines)

    system_prompt = f"""You are a Senior Technical Auditor with deep expertise in reading Git history.

You have access to real commit messages and actual code diffs (added/removed lines).

Rules:
- When you see a diff like '- timeout = 5' and '+ timeout = 10', explicitly state the value changed from 5 to 10.
- Always cite the commit hash and author when referencing a specific change.
- If the context doesn't contain enough information to answer, say so clearly — do not hallucinate.
- Keep answers concise and technical. Avoid filler sentences.{filter_note}
"""

    messages = [{"role": "system", "content": system_prompt}]

    recent_history = history[-(HISTORY_WINDOW * 2):]
    for msg in recent_history:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    user_message = f"""--- RELEVANT COMMIT HISTORY ---
{context}
--- QUESTION ---
{query}
"""
    messages.append({"role": "user", "content": user_message})
    return messages


def ask(
    query: str,
    history: list,
    author: str = None,
    start_date: str = None,
    end_date: str = None,
):
    """
    Query the RAG pipeline with reranking and optional metadata filters.

    Pipeline: ChromaDB (top 10) → CrossEncoder reranker → top 3 → Groq LLM
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")

    context, filters_active = _build_context(query, author, start_date, end_date)
    messages = _build_messages(
        query, context, history,
        author=author,
        start_date=start_date,
        end_date=end_date,
        filters_active=filters_active,
    )

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