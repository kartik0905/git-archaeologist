# Git Archaeologist - Project Context Prompt

## Project Overview

**Git Archaeologist** is a RAG (Retrieval-Augmented Generation) based tool that enables users to query the **history** of any Git repository in plain English. Unlike tools that analyze current code, this project focuses on understanding **why code became what it is** by searching through commit history, diffs, and metadata.

### Key Features:

- 🗂️ **Searchable Git History**: Turn any repository's commit history into a vector database
- 🤖 **AI-Powered Queries**: Ask questions about what changed, why, and when
- 📊 **Multi-Stage Retrieval**: Combines vector similarity (ChromaDB) + cross-encoder reranking for precision
- 🔒 **Private Repo Support**: Inject GitHub PAT for private repository access
- 📄 **PDF Export**: Generate audit reports of conversation history
- ⏱️ **Configurable Depth**: Query recent history or the entire repository
- 🔍 **Filtering**: Filter results by author, date range

### Tech Stack:

| Component       | Technology                                 |
| --------------- | ------------------------------------------ |
| Frontend        | Streamlit (web UI)                         |
| LLM             | Groq - `llama-3.3-70b-versatile`           |
| Vector Database | ChromaDB (persistent storage)              |
| Embeddings      | `all-MiniLM-L6-v2` (sentence-transformers) |
| Reranker        | `cross-encoder/ms-marco-MiniLM-L-6-v2`     |
| Git Parsing     | GitPython                                  |
| PDF Export      | fpdf2                                      |

---

## File-by-File Breakdown

### 1. **app.py** - Streamlit Web Interface

**Purpose**: The main entry point and user-facing UI

**What it does:**

- Initializes Streamlit page configuration (title, layout, icon)
- Manages session state (repo URL, messages, filters, dates, etc.)
- Provides sidebar controls for:
  - Repository URL input
  - GitHub PAT for private repos
  - "Excavation depth" selector (how many commits to analyze)
  - Groq API key configuration
- Renders chat interface for multi-turn conversation
- Handles repo indexing and query submission
- Generates PDF export of conversation history

**Key Variables:**

- `repo_loaded`: Boolean flag indicating if repo has been indexed
- `messages`: List of conversation turns (Q&A pairs)
- `repo_url`: GitHub repository URL
- `author_filter`: Optional filter by commit author
- `start_date`, `end_date`: Optional date range filters

**User Flow:**

1. User enters repo URL and optional GitHub PAT
2. Selects excavation depth (100 recent, 500 quarterly, 2000 yearly, or all)
3. Clicks "Index Repository" → calls `run_indexing()` from indexer.py
4. Once indexed, user can ask questions in chat interface
5. Each question triggers `ask()` from qa.py
6. Responses are streamed back and displayed
7. User can export conversation as PDF

---

### 2. **indexer.py** - Repository Indexing Pipeline

**Purpose**: Clone a repository and build a searchable vector database from its commit history

**Key Functions:**

#### `_get_embedding_function()`

- Returns a SentenceTransformerEmbeddingFunction using `all-MiniLM-L6-v2`
- Used by ChromaDB for converting commits to embeddings

#### `get_collection()`

- Retrieves an existing ChromaDB collection named "git_commits"
- Called after indexing is complete, before querying

#### `_clone_repo(repo_url, commit_limit, token, status_text)`

- Clones the repository from GitHub (public or private)
- Injects GitHub PAT into URL if provided (via `inject_github_token()`)
- Uses **shallow cloning** (`--depth=N`) if commit_limit is set (faster for large repos)
- Uses full clone if `commit_limit == 0`
- Returns True on success, False on failure
- Updates status messages in Streamlit UI

#### `_validate_repo(repo_url, token, status_text)`

- Verifies the repository URL is valid and accessible
- Checks URL format (http/https)
- Uses `git ls-remote` to confirm repo exists
- Handles different error types (not found, authentication failed, etc.)
- Returns boolean success status

#### `_index_commits(commit_limit, status_text, progress_bar)`

- Mines commits using the `load_git_history()` generator from miner.py
- Creates/recreates ChromaDB collection
- Batches commits (BATCH_SIZE = 10) for efficient insertion
- For each commit, creates metadata:
  - `author`: Commit author name
  - `timestamp`: Unix timestamp for date filtering
  - `message`: Commit message
  - `hash`: Short commit hash
  - `content`: The diff hunks (most important for retrieval)
- Updates progress bar as commits are processed
- Returns total number of indexed commits

#### `run_indexing(repo_url, commit_limit, token)`

- Main orchestration function called from app.py
- Validates repo → Clones repo → Indexes commits → Returns success status
- Cleans up temp files on failure

**Data Flow:**

```
repo_url + token → _validate_repo()
    → _clone_repo() → temp_repo_clone/
    → load_git_history() generator (miner.py)
    → Batch process commits → ChromaDB collection "git_commits"
```

---

### 3. **miner.py** - Commit History Parser

**Purpose**: Extract commits and diffs from a Git repository, yielding them one at a time as a memory-efficient generator

**Key Variables:**

- `IGNORE_EXTENSIONS`: Binary/compiled file types to skip (.png, .jpg, .json, .lock, etc.)
- `IGNORE_DIRS`: Directories to ignore (node_modules, dist, **pycache**, etc.)

**Key Functions:**

#### `should_ignore(file_path)`

- Boolean check: should this file be skipped during diff analysis?
- Returns True if file has an ignored extension or is in an ignored directory
- Reduces noise and speeds up indexing

#### `load_git_history(repo_path, branch="main", limit=None)`

- **Generator function** (yields commits one at a time, not loading all into memory)
- Iterates through commit history on the specified branch
- Gracefully falls back to current HEAD if "main" doesn't exist
- Respects `max_count=limit` for partial history

**Yield Structure** (for each commit):

```python
{
    "hash": "<sha1>",
    "message": "<commit message>",
    "author": "<author name>",
    "date": "<YYYY-MM-DD HH:MM:SS>",
    "timestamp": <unix_timestamp>,
    "diff_summary": """
        File: path/to/file.py
        @@ -10,5 +10,6 @@
         def function():
        -    old_line
        +    new_line
    """
}
```

**Diff Chunking Strategy** (Key Engineering Decision):

- **NOT character-truncated**: Instead of cutting diffs at 1200 chars, splits at `@@` (hunk boundaries)
- Each hunk (logical code block) is kept intact
- Truncation only happens if multiple hunks exceed 1200 chars
- Allows LLM to see complete, meaningful code changes (e.g., "value changed from 5 to 10")

**Performance:**

- Generator pattern = O(1) memory (only 1 commit in memory at a time)
- Shallow cloning (from indexer.py) keeps Git fetch fast
- Ignores large/binary files automatically

---

### 4. **qa.py** - Query Processing & Retrieval

**Purpose**: Handle multi-turn conversations by rewriting queries, retrieving relevant commits, reranking, and generating LLM responses

**Key Constants:**

- `HISTORY_WINDOW = 5`: Last 5 turns included in every LLM call for context-aware responses
- `RETRIEVAL_K = 10`: Initial retrieval from ChromaDB (before reranking)
- `RERANK_TOP_N = 3`: Final commits passed to LLM after reranking

**Key Functions:**

#### `_get_reranker()`

- Lazy-loads CrossEncoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) on first use
- ~85MB download, cached by sentence-transformers
- Improves retrieval precision over vector similarity alone

#### `_rerank(query, docs)`

- Scores each (query, doc) pair using the cross-encoder
- Sorts by relevance score (descending)
- Returns top N documents only (RERANK_TOP_N = 3)
- **Purpose**: Pure vector similarity returns commits that "look" related; reranker ensures they actually answer the question

#### `_build_where_clause(author, start_date, end_date)`

- Constructs ChromaDB metadata filters
- Converts date strings to Unix timestamps for numeric comparison
- Supports combined filters with `$and` operator
- Returns None if no filters are active

#### `_classify_query(query)`

- Uses LLM to classify user query as:
  - **"listing"**: Chronological queries (most recent, last N, first commit, newest)
  - **"semantic"**: Specific changes, reasons, bugs, features, authorship
- Used to determine retrieval strategy

#### `ask(query, history, author_filter, start_date, end_date)`

- **Main function** called from app.py on each user question
- **Steps**:
  1. Rewrite query using conversation history (resolve vague references)
  2. Build metadata filter from author/date inputs
  3. Retrieve top RETRIEVAL_K commits from ChromaDB by vector similarity
  4. Rerank to top RERANK_TOP_N using cross-encoder
  5. Stream response from Groq LLM (llama-3.3-70b-versatile)
  6. Citations include commit hash, author, date
  7. Return answer + metadata for display

**Query Rewriting Logic** (Key Feature):

- Follow-up like "who worked on it?" is rewritten to a standalone search query
- LLM uses conversation history to resolve vague references
- Retrieval becomes context-aware, not keyword-based

**Two-Stage Retrieval** (Key Engineering Decision):

- **Stage 1**: ChromaDB vector similarity (fast, broad recall)
- **Stage 2**: Cross-encoder reranking (slow, high precision)
- Trade-off: Precision over recall → best 3 results fed to LLM

---

### 5. **utils.py** - Utility Functions

**Purpose**: Helper functions for cleanup, token injection, and PDF generation

**Key Constants:**

- `TEMP_REPO_PATH = "./temp_repo_clone"`: Directory where repos are cloned
- `CHROMA_PATH = "./chroma_db"`: ChromaDB storage directory

**Key Functions:**

#### `remove_readonly(func, path, excinfo)`

- Helper for `shutil.rmtree()` to handle read-only files
- Changes file permissions before deletion
- Gracefully handles permission errors

#### `cleanup_temp_data(*args, **kwargs)`

- Recursively removes temp_repo_clone/ and chroma_db/ directories
- Called on app exit (registered with `atexit`)
- Also called on explicit reset button
- **Security**: Ensures no sensitive repository data persists on disk

#### `inject_github_token(repo_url, token)`

- Injects GitHub PAT into HTTPS URLs for authentication
- Parses URL, inserts token before hostname
- **Security**: Token never written to disk, only held in memory during clone
- Returns authenticated URL or original URL if no token provided
- Raises error if token provided with non-HTTPS URL

#### `create_pdf(repo_url, messages)`

- Generates a PDF audit report of the conversation
- Includes:
  - Title: "Legacy Code Archaeologist - Audit Report"
  - Repository URL
  - Timestamp
  - All Q&A pairs from conversation
- Returns PDF as bytes
- Used for exporting conversation history

---

## Project Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    USER (Streamlit UI)                       │
└──────────────────────────────────────────────────────────────┘
                           ↓
              [Repo URL + GitHub PAT + Depth]
                           ↓
    ┌─────────────────────────────────────────────────────────┐
    │              INDEXING PIPELINE                           │
    │                                                          │
    │  1. indexer.py → _validate_repo()                       │
    │  2. indexer.py → _clone_repo()                          │
    │                    ↓                                     │
    │              ./temp_repo_clone                           │
    │                    ↓                                     │
    │  3. miner.py → load_git_history() (generator)           │
    │                    ↓                                     │
    │            {hash, message, author, diffs}               │
    │                    ↓                                     │
    │  4. indexer.py → _index_commits()                       │
    │       Batch insert into ChromaDB                         │
    │                    ↓                                     │
    │              ./chroma_db (persisted)                     │
    │                                                          │
    └─────────────────────────────────────────────────────────┘
                           ↓
              [Indexed! Ready to query]
                           ↓
    ┌─────────────────────────────────────────────────────────┐
    │              QUERY PIPELINE                              │
    │                                                          │
    │  User Question + Conversation History                   │
    │  + optional filters (author, dates)                     │
    │                    ↓                                     │
    │  1. qa.py → ask()                                       │
    │     - Rewrite query with LLM (context-aware)            │
    │     - Build ChromaDB where clause                       │
    │                    ↓                                     │
    │  2. ChromaDB retrieval (top 10 by vector similarity)    │
    │                    ↓                                     │
    │  3. qa.py → _rerank() (cross-encoder)                   │
    │     Keep only top 3                                      │
    │                    ↓                                     │
    │  4. Groq LLM (llama-3.3-70b-versatile)                  │
    │     Stream response with citations                      │
    │                    ↓                                     │
    │           Answer + metadata                             │
    │                                                          │
    └─────────────────────────────────────────────────────────┘
                           ↓
              [Display in Streamlit chat]
                           ↓
         [Optional: Export as PDF audit report]
```

---

## Key Engineering Decisions

### 1. **Hunk-Based Diff Chunking** (miner.py)

- Splits diffs at `@@` boundaries instead of truncating at character limit
- Allows LLM to see complete code changes
- Example: "the value changed from 5 to 10" vs. "truncated hunk"

### 2. **Two-Stage Retrieval** (qa.py)

- **Stage 1**: Vector similarity (broad, fast)
- **Stage 2**: Cross-encoder reranking (narrow, precise)
- Results in top 3 most relevant commits fed to LLM
- Trades latency for accuracy

### 3. **Query Rewriting with History** (qa.py)

- Vague follow-ups ("who worked on it?") are rewritten to standalone queries
- LLM uses conversation history to resolve references
- Makes retrieval context-aware without modifying the query manually

### 4. **Shallow Cloning** (indexer.py)

- For large repos, `git clone --depth=N` is exponentially faster
- Configurable via UI (Recent/Quarterly/Yearly/Everything)
- Only full clone when user selects "Everything"

### 5. **Generator-Based Mining** (miner.py)

- Commits are yielded one at a time, not loaded into memory
- O(1) memory usage regardless of repository size
- Crucial for indexing massive projects

### 6. **Token Injection at Runtime** (utils.py)

- GitHub PAT never written to disk
- Injected into clone URL only during cloning
- Immediately cleaned up afterward
- Wiped completely on app exit

### 7. **Metadata Filtering** (qa.py)

- Author and date filters are pushed down to ChromaDB `where` clauses
- Unix timestamps enable numeric range comparisons
- If no results match filters, tool explicitly says so (no silent fallback)

---

## Testing

**Tests located in**: `tests/` directory

- `test_miner.py`: Tests commit mining and diff parsing
- `test_qa.py`: Tests query rewriting and retrieval
- `test_utils.py`: Tests utility functions (token injection, cleanup, etc.)
- **Total**: 49 passing tests
- **No external services required**: All tests are self-contained

---

## Security Considerations

✅ **GitHub PAT**: Never persisted to disk, held only in memory during clone
✅ **Temp files**: Aggressively cleaned up on reset or app exit
✅ **Private repos**: Full support via authenticated cloning
✅ **Token visibility**: Masked in Streamlit UI (type="password")
✅ **Cleanup on crash**: Registered with `atexit` module

---

## Dependencies Summary

**Core Libraries**:

- `streamlit`: Web UI framework
- `chromadb`: Vector database (embeddings + persistence)
- `gitpython`: Git repository parsing
- `sentence-transformers`: Embeddings and cross-encoder reranking
- `openai`: Groq API client (compatible with OpenAI SDK)
- `fpdf2`: PDF generation
- `python-dotenv`: Environment variable loading

**Python Version**: 3.12+

**Groq Models Used**:

- `llama-3.3-70b-versatile`: Main LLM for answering and query rewriting
- `all-MiniLM-L6-v2`: Embeddings for commits
- `cross-encoder/ms-marco-MiniLM-L-6-v2`: Reranking model

---

## How to Use (Quick Start)

1. **Install dependencies**: `pip install -r requirements.txt` (or `uv sync`)
2. **Set environment variables**:
   ```bash
   export GROQ_API_KEY="gsk_your_key"
   ```
3. **Run Streamlit**:
   ```bash
   streamlit run app.py
   ```
4. **Index a repository**:
   - Enter repo URL (e.g., `https://github.com/pallets/flask.git`)
   - Select excavation depth
   - Click "Index Repository"
5. **Ask questions**:
   - "When was the authentication system added?"
   - "Who worked on the database migrations?"
   - "What changed in the API last month?"
6. **Export results**:
   - Click "Download Audit Report" to export PDF

---

## Summary

**Git Archaeologist** is a sophisticated RAG system that transforms Git history into a queryable knowledge base. It combines:

- **Efficient mining** (generator-based, shallow cloning)
- **Precise retrieval** (vector + reranking)
- **Context-aware** conversation (history injection + query rewriting)
- **User-friendly interface** (Streamlit UI with filtering)
- **Security best practices** (no persistent tokens, aggressive cleanup)

The project demonstrates modern AI/ML engineering: from data pipelines (mining → indexing) to retrieval (dual-stage) to generation (streaming LLM).
