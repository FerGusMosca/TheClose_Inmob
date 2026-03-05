# zChatbotAgentFwk

## 🚀 Quick Start  

1. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Linux/Mac
   venv\Scripts\activate      # On Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables** in `.env`:
   ```
   OPENAI_API_KEY=sk-...
   BOT_PROFILE=generic   # or lawyer
   ```

4. **Run the app**
   ```bash
   uvicorn main:app --reload
   ```

---

## 📂 Project Structure (relevant parts)

```
config/
controllers/
data/
  documents/
logic/
  pipeline/
    hybrid_bot.py
    prompt_based_chatbot.py
intents/
  detector.py
  slots.py
  registry.py
  handlers/
prompts/
  generic.txt
  lawyer.txt
vectorstores/
```

---

## 🔄 Hybrid Flow

- **RAG mode**  
  If the retriever returns relevant documents → build context and answer **citing those documents**.

- **Fallback mode**  
  If no relevant documents are found → use **prompt-only bot** (same system prompt, no fake citations).

---

## 📝 Logging

- Centralized in: `common/util/logging.py`  
- Key fields to log:
  - `mode` → `rag` or `fallback`
  - `docs_found` → number of docs retrieved
  - `query[:200]` → first 200 chars of the query

---

## ✅ Tests to Add

- `tests/test_rag_docs.py`  
  Covered question → must cite documents and respect bot style.

- `tests/test_fallback.py`  
  Out-of-corpus question → must **NOT** cite documents and must respect bot style.

- `tests/test_intents.py`  
  Detect intent, request missing slots, and execute handler.
