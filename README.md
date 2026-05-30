# Legacy Code Archaeologist

A RAG-based tool that lets you query the **history** of any Git repository in plain English — not the current code, but *why it became what it is*.

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Web%20UI-red)
![Groq](https://img.shields.io/badge/Groq-LLaMA--3.3--70B-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Tests](https://img.shields.io/badge/Tests-49%20passing-brightgreen)

---

## Architecture

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│   Git Repo URL  │────▶│     indexer.py       │────▶│      ChromaDB        │
│ (public/private)│     │ Clone → Parse Diffs  │     │  Commit Embeddings   │
└─────────────────┘     │ Batch → Embed        │     │  + Metadata          │
                        └─────────────────────┘     └──────────┬───────────┘
                                                               │
                        ┌──────────────────────────────────────┘
                        ▼
 ┌────────────┐   Step 1: Retrieve    ┌──────────────────────────────────┐
 │ User Query │──────────────────────▶│ ChromaDB — top 10 by similarity  │
 │            │                       └──────────────┬───────────────────┘
 │            │                                      │
 │            │   Step 2: Rerank      ┌──────────────▼───────────────────┐
 │            │──────────────────────▶│ Cross-Encoder — scored, top 3    │
 │            │                       └──────────────┬───────────────────┘
 │            │                                      │
 │            │   Step 3: Generate    ┌──────────────▼───────────────────┐
 │            │──────────────────────▶│ Groq LLM (llama-3.3-70b)         │
 └────────────┘   + chat history      │ + diff context + active filters  │
                  + metadata filters  └──────────────┬───────────────────┘
                                                     │
                                                     ▼
                                          Streamed answer
                                          with commit citations
```

---

## Demo

https://github.com/user-attachments/assets/8e2e7c88-7425-4a7b-bdcf-c871f8e55591


---

## Key engineering decisions

**Two-stage retrieval (ChromaDB + reranker)**
Pure vector similarity returns commits that *look* related. The cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores each result against your exact question and keeps only the top 3. Precision over recall.

**Hunk-based diff chunking**
Diffs are split at `@@` boundaries, not truncated at a character limit. The LLM sees complete, meaningful code hunks — so it can say "the value changed from 5 to 10" rather than a vague summary.

**Metadata filtering**
Author name and date range filters are pushed down to ChromaDB `where` clauses — the reranker only sees commits that already match your filter.

**Multi-turn conversation**
Last 5 turns of chat history are injected into every LLM call. Follow-up questions work without repeating context.

**Private repo support**
GitHub PAT is injected into the clone URL at runtime via `urlparse` — never written to disk, wiped on reset.

**O(1) memory mining**
The commit iterator is a Python generator. Shallow cloning (`--depth`) keeps fetches fast for recent history queries.

---

## Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq — `llama-3.3-70b-versatile` |
| Vector DB | ChromaDB |
| Embeddings | `all-MiniLM-L6-v2` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Git parsing | GitPython |
| Package manager | uv |

---

## Project structure

```
├── app.py          # Streamlit UI
├── indexer.py      # Clone + batch-index into ChromaDB
├── qa.py           # Retrieval → reranking → LLM call
├── miner.py        # Generator-based diff parser
├── utils.py        # PDF export, cleanup, token injection
└── tests/          # 49 tests, no external services required
```

---

## Installation

```bash
git clone https://github.com/kartik0905/git-archaeologist.git
cd git-archaeologist
uv pip install -r requirements.txt
cp .env.example .env   # add your Groq API key
streamlit run app.py
```

> The first query downloads the reranker model (~90MB) and caches it locally. All subsequent runs load from cache.

---

## Known limitations

- Chat history is passed to the LLM but not used to rewrite ChromaDB queries. Vague follow-ups like *"what else did they change?"* may retrieve different commits than expected.
- Author filtering requires an exact Git config name match.
- Reranker runs on CPU — adds ~1–2 seconds per query on large result sets.

---

## Build by Kartik Garg