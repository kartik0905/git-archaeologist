# 🏛️ Legacy Code Archaeologist

> **An AI-powered system that lets you talk to the *history* of any GitHub repository — not just its current code.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Web%20UI-red)
![Groq](https://img.shields.io/badge/Groq-LLaMA--3.3--70B-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

Legacy Code Archaeologist is a production-grade **Retrieval-Augmented Generation (RAG)** tool designed to analyze *how* and *why* a codebase evolved over time.  
Instead of reading static snapshots, it mines **actual Git diffs**, allowing you to ask high-impact questions like:

- *“Who introduced the timeout bug..?”*  
- *“Why was the authentication logic rewritten in 2021?”*  
- *“When did this API contract change?”*  

Built for scalability, accuracy, and real-world engineering workflows, now supercharged by Groq's lightning-fast inference engine.

---

## 🚀 Key Features

### 🔍 Deep Git History Intelligence
- Parses **real commit diffs** (added/removed lines) — not just file snapshots.
- Understands *why* code changed, not just *what* changed.

### ⚡ High-Performance Mining Engine
- Generator-based architecture enables **O(1) memory usage**.
- Handles massive repositories (Linux, React, Kubernetes) efficiently.

### 🧠 AI-Powered Q&A
- Uses **Groq API (LLaMA-3.3-70B)** for lightning-fast, highly accurate contextual reasoning.
- Powered by **ChromaDB** for semantic search over commit history.

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
- Python 3.12+
- GitPython (Custom Mining Engine)
- ChromaDB (Local Vector Store)

**AI Engine**
- Groq API (`llama-3.3-70b-versatile` via OpenAI compatible endpoint)

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
│      Groq API       │  ← Lightning-fast LLM reasoning
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
3. Provide your Free Groq API Key via the UI (if not set in `.env`).
4. Ask natural language questions:
   - “Why was this function refactored?”
   - “Who changed the authentication logic?”
5. Export a **PDF audit report** if needed.

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
*(Or use `uv pip install -r requirements.txt` for faster installation)*

### 3️⃣ Configure environment variables
Create a `.env` file:
```env
GROQ_API_KEY=your_groq_api_key_here
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
├── requirements.txt
└── pyproject.toml
```

---

## 🧠 Why This Project Stands Out

- Designed like a **real production system**, not a demo.
- Handles **large-scale repositories** efficiently.
- Solves a *real developer pain point* — understanding legacy code.
- Uses **Groq** to eliminate LLM latency, making log parsing instantaneous.

---

## 📜 License

MIT License

---

## ⭐ If You Like This Project
Star the repository and feel free to contribute or fork it for your own tooling.

---

**Built with engineering discipline, not just prompts.**
