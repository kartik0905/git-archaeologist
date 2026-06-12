import os
from datetime import datetime
from openai import OpenAI
from indexer import get_collection
from functools import lru_cache

# How many past messages to include for conversation context
HISTORY_WINDOW = 5
# How many commits to fetch from ChromaDB before reranking
RETRIEVAL_K = 10
# How many to pass to the LLM after reranking
RERANK_TOP_N = 3


@lru_cache(maxsize=1)
def _get_reranker():
    """
    Lazy-load the cross-encoder reranker on first use.
    Downloads ~85MB on first call, then cached by sentence-transformers.
    """
    from sentence_transformers import CrossEncoder
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


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
        ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        conditions.append({"timestamp": {"$gte": ts}})

    if end_date:
        ts = int(datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp())
        conditions.append({"timestamp": {"$lte": ts}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _classify_query(query: str) -> str:
    """
    Use LLM to classify query as 'listing' or 'semantic'.
    - listing: ordered/sequential queries (most recent, last N, first commit, newest)
    - semantic: specific changes, reasons, authors, bugs, features
    """
    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""Classify this Git repository question into one of two types:

- "listing": questions asking for ordered/sequential commits (most recent, last N, first commit, latest, newest, chronological list)
- "semantic": questions asking about specific changes, reasons, authors, bugs, features

Reply with ONLY one word: listing or semantic.

Question: "{query}"
"""
        }],
        max_tokens=5
    )

    result = response.choices[0].message.content.strip().lower()
    return "listing" if "listing" in result else "semantic"


def _get_ordered_commits(query: str, n: int = 5) -> str:
    """
    Fetch commits directly from ChromaDB ordered by timestamp.
    Used for listing/ordering queries that RAG can't handle reliably.
    """
    collection = get_collection()
    results = collection.get(
        limit=500,
        include=["metadatas", "documents"]
    )

    docs = results["documents"]
    metas = results["metadatas"]

    # Sort by timestamp descending (most recent first)
    paired = sorted(
        zip(metas, docs),
        key=lambda x: x[0].get("timestamp", 0),
        reverse=True
    )

    # Reverse for first/earliest queries
    if any(kw in query.lower() for kw in ["first", "earliest", "initial"]):
        paired = list(reversed(paired))

    top = paired[:n]
    context = ""
    for i, (meta, doc) in enumerate(top):
        context += f"--- COMMIT {i + 1} ---\n{doc}\n\n"

    return context


def _rewrite_query(query: str, history: list) -> str:
    """
    Use LLM to rewrite a vague follow-up into a standalone search query.
    If no history exists, returns the original query unchanged.
    """
    if not history:
        return query

    recent = history[-(HISTORY_WINDOW * 2):]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent
    )

    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""Given this conversation history:
{history_text}

Rewrite this follow-up question as a standalone search query (one sentence, no explanation):
"{query}"
"""
        }],
        max_tokens=60
    )

    return response.choices[0].message.content.strip()


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

    # If filters were active but returned nothing, signal clearly
    if where and not docs:
        return "No commits found matching the active filters.", True

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
- Keep answers concise and technical. Avoid filler sentences.
- For listing queries (last N commits, recent commits), present them in order with commit hash, author, date and message.{filter_note}
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

    Pipeline: classify → (listing: ordered fetch) | (semantic: rewrite → ChromaDB → rerank) → Groq LLM
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")

    # Classify query type
    query_type = _classify_query(query)

    if query_type == "listing":
        # Extract number from query if present e.g. "last 10 commits"
        n = 5
        for num in ["10", "7", "6", "5", "4", "3", "2"]:
            if num in query:
                n = int(num)
                break
        context = _get_ordered_commits(query, n=n)
        filters_active = False
    else:
        search_query = _rewrite_query(query, history)
        context, filters_active = _build_context(search_query, author, start_date, end_date)

    MAX_CONTEXT_CHARS = 12000
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...(context truncated)"

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