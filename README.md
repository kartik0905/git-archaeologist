# 🏛️ Legacy Code Archaeologist

> **An AI-powered system that lets you talk to the *history* of any GitHub repository — not just its current code.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Web%20UI-red)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1--nano-teal)
![License](https://img.shields.io/badge/License-MIT-yellow)

Legacy Code Archaeologist is a production-grade **Retrieval-Augmented Generation (RAG)** tool designed to analyze *how* and *why* a codebase evolved over time.  
Instead of reading static snapshots, it mines **actual Git diffs**, allowing you to ask high-impact questions like:

- *“Who introduced the timeout bug?”*  
- *“Why was the authentication logic rewritten in 2021?”*  
- *“When did this API contract change?”*  

Built for scalability, accuracy, and real-world engineering workflows.

---

## 🚀 Key Features

### 🔍 Deep Git History Intelligence
- Parses **real commit diffs** (added/removed lines) — not just file snapshots.
- Understands *why* code changed, not just *what* changed.

### ⚡ High-Performance Mining Engine
- Generator-based architecture enables **O(1) memory usage**.
- Handles massive repositories (Linux, React, Kubernetes) efficiently.

### 🧠 AI-Powered Q&A
- Uses **OpenAI GPT-3.5 Turbo** for contextual reasoning.
- Powered by **LangChain + ChromaDB** for semantic search over commit history.

### 🕰️ Time Machine Mode
- Switch between:
  - **Recent History (Fast Scan)**
  - **Deep Excavation (Full Repo Analysis)**

### 📊 Audit-Grade Reporting
- Automatically generates **PDF audit reports** of chat sessions.
- Ideal for compliance, audits, and engineering reviews.

### 🧹 Smart Resource Management
- Shallow Git clones (`--depth`) for 99% faster fetches.
- Auto-cleanup of cloned repos and vector databases.

---

## 🧱 Tech Stack

**Backend**
- Python 3.10+
- GitPython (Custom Mining Engine)
- LangChain
- ChromaDB (Local Vector Store)

**AI Engine**
- OpenAI GPT-3.5 Turbo

**Frontend**
- Streamlit

**DevOps / Tooling**
- uv (Fast Python package manager)
- python-dotenv

---

## 🧭 System Architecture

```
┌──────────────┐
│   Git Repo   │
└──────┬───────┘
       ↓
┌─────────────────────┐
│  Custom Miner Engine│  ← Generator-based diff processing
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│   ChromaDB Vector   │  ← Semantic indexing
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│  OpenAI GPT-3.5 API │  ← Reasoning & answers
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│   Streamlit UI      │  ← Chat + Time Controls
└─────────────────────┘
```

---

## 🖥️ Demo / Usage

1. Paste any **public GitHub repository URL**
2. Select:
   - **Fast Mode** → Recent commits only
   - **Deep Mode** → Full historical analysis
3. Ask natural language questions:
   - “Why was this function refactored?”
   - “Who changed the authentication logic?”
4. Export a **PDF audit report** if needed.

---

## ⚙️ Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/kartik0905/git-archaeologist.git
cd git-archaeologist
```

### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Configure environment variables
Create a `.env` file:
```env
OPENAI_API_KEY=your_api_key_here
```

### 4️⃣ Run the application
```bash
streamlit run app.py
```

---

## 🗂️ Project Structure

```
.
├── app.py              # Streamlit UI & user interaction
├── miner.py            # Core mining engine (diff parsing, batching)
├── vector_store.py     # ChromaDB integration
├── prompts/            # LLM prompt templates
├── utils/              # Helpers & cleanup logic
├── reports/            # Generated PDF audit reports
└── requirements.txt
```

---

## 🧠 Why This Project Stands Out

- Designed like a **real production system**, not a demo.
- Handles **large-scale repositories** efficiently.
- Solves a *real developer pain point* — understanding legacy code.
- Built with extensibility in mind (CI analysis, PR reviews, blame tracking).

---

## 📜 License

MIT License

---

## ⭐ If You Like This Project
Star the repository and feel free to contribute or fork it for your own tooling.

---

**Built with engineering discipline, not just prompts.**
