# 🧠 Legacy Code Archaeologist
**Chat with the history of any GitHub repository — understand _why_ code changed, not just _what_ changed.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Web%20UI-red)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1--nano-teal)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🚀 Overview

**Legacy Code Archaeologist** is a Retrieval-Augmented Generation (RAG) system that allows developers to deeply analyze the history of any public GitHub repository.

Instead of manually inspecting commits, this tool enables natural-language questions like:

- *Why was this timeout increased?*
- *Who introduced this bug?*
- *When did this logic change and why?*

It reads **actual code diffs**, not just commit messages, and uses AI to generate accurate, contextual explanations.

---

## ✨ Key Features

### 🔍 Deep Git Diff Intelligence
- Parses real `+/-` code diffs from commits
- Tracks logic changes, refactors, and parameter updates

### ⚡ Dynamic Repository Loading
- Accepts any public GitHub URL
- Automatically clones and indexes the repository

### 🧠 RAG-Powered Q&A
- Embeddings stored in **ChromaDB**
- Semantic search powered by **SentenceTransformers**
- Reasoning performed by **OpenAI GPT-3.5 Turbo**

### 🧾 Streaming Responses
- Token-by-token response streaming (ChatGPT-like UX)

### 📄 PDF Export
- Export chat history and audit trails as clean PDF reports

### 🧹 Automatic Cleanup
- Deletes cloned repos and vector databases after use

### 🔐 Secure by Design
- API keys stored using environment variables
- No secrets committed to source control

---

## 🧱 Tech Stack

| Layer | Technology |
|------|------------|
| Language | Python |
| UI | Streamlit |
| Git Mining | GitPython |
| Vector DB | ChromaDB |
| Embeddings | SentenceTransformers |
| LLM | OpenAI GPT-3.5 |
| PDF Export | FPDF |
| Package Manager | uv / pip |

---

## 📦 Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/kartik0905/git-archaeologist.git
cd git-archaeologist
```

### 2️⃣ Create virtual environment
```bash
uv venv
source .venv/bin/activate
```

### 3️⃣ Install dependencies
```bash
uv pip install -r requirements.txt
```

### 4️⃣ Configure environment variables
Create a `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key
```

---

## ▶️ Running the App

```bash
streamlit run app.py
```

Open the provided local URL in your browser.

---

## 🧠 How It Works

```
GitHub Repo
   ↓
Git Commit History + Diffs
   ↓
Chunking & Embeddings
   ↓
ChromaDB Vector Store
   ↓
Semantic Retrieval
   ↓
LLM Reasoning (GPT‑4.1 nano)
```

---

## 🛣️ Roadmap

- GitHub OAuth for private repositories  
- Visual diff timelines  
- Multi-repo analysis  
- Test impact analysis  
- VS Code extension  

---

## 📜 License

MIT License

---

**Built for developers who want to understand *why* the code exists — not just what it does.**
