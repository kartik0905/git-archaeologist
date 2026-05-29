import os
from openai import OpenAI
from indexer import get_collection

# How many past messages to include for conversation context
HISTORY_WINDOW = 5
# How many commits to retrieve from vector DB per query
TOP_K = 5


def _build_where_clause(author: str = None, start_date: str = None, end_date: str = None) -> dict | None:
    """
    Build a ChromaDB `where` clause from optional filters.
    ChromaDB supports $and, $eq, $gte, $lte operators.
    Returns None if no filters are active.
    """
    conditions = []

    if author and author.strip():
        conditions.append({"author": {"$eq": author.strip()}})

    if start_date:
        conditions.append({"date": {"$gte": start_date}})

    if end_date:
        # Append end-of-day so the full end date is included
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
    Retrieve the top-K most relevant commits from ChromaDB.
    Applies metadata filters if provided.
    Returns (context_string, filters_were_active).
    """
    collection = get_collection()
    where = _build_where_clause(author, start_date, end_date)
    filters_active = where is not None

    try:
        if where:
            results = collection.query(
                query_texts=[query],
                n_results=TOP_K,
                where=where
            )
        else:
            results = collection.query(query_texts=[query], n_results=TOP_K)
    except Exception:
        # ChromaDB throws if the where clause matches 0 documents
        # Fall back to unfiltered so the user gets an honest "no results" answer
        results = collection.query(query_texts=[query], n_results=TOP_K)
        filters_active = False  # signal to caller that filters were dropped

    context = ""
    if results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
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
    """
    Construct the full message list for the LLM.
    Includes active filter context so the model knows the scope.
    """
    # Build a filter summary line for the system prompt
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

    # Inject the last N turns of conversation for multi-turn awareness
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
    Query the RAG pipeline with optional metadata filters.

    Args:
        query:      The user's current question.
        history:    Full chat history so far (current query NOT included).
        author:     Optional exact author name filter.
        start_date: Optional ISO date string 'YYYY-MM-DD'.
        end_date:   Optional ISO date string 'YYYY-MM-DD'.

    Returns:
        A streaming generator for st.write_stream.
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