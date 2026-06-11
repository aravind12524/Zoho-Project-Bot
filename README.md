# Zoho Project Bot

A conversational AI assistant for Zoho Projects built with FastAPI (backend) and React/Vite (frontend). It integrates with Zoho Projects API, supports OAuth login, provides natural‑language summaries, task creation, and long‑term memory.

## Setup Steps

### Backend
```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy .env.example to .env and fill values)
cp .env.example .env   # adjust paths on Windows
```

Run the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd ../frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:3000`.

## OAuth Configuration Guide
1. Register a Zoho OAuth client at the Zoho API Console.
2. Set the **Redirect URI** to `http://localhost:8000/auth/callback`.
3. Add the following variables to `.env`:
   - `ZOHO_CLIENT_ID`
   - `ZOHO_CLIENT_SECRET`
   - `ZOHO_REDIRECT_URI`
   - `ZOHO_REFRESH_TOKEN` (optional, for offline access)
4. Restart the backend after updating `.env`.

## Architecture Overview
- **Backend (FastAPI)**
  - `main.py` – entry point, defines auth routes.
  - `agents/` – QueryAgent, ActionAgent, MemoryAgent.
  - `zoho_client.py` – low‑level Zoho API wrapper.
  - `graph.py` – long‑term memory graph handling.
- **Frontend (React + Vite)**
  - `ChatUI.jsx` – renders markdown‑rich chat messages.
  - `LoginScreen.jsx` – OAuth login flow.
  - `ConfirmationModal.jsx` – HIL confirmation dialogs.
- **LLM Integration**
  - `llm.py` – Groq/Gemini fallback chain.
  - Prompts are passed to LLM to generate natural responses.

## ✅ Demonstration Checklist
- **OAuth login** – user authenticates via Zoho and receives a token.
- **Four conversation flows** – e.g., list projects, list tasks, create task, get utilization.
- **Delete/Update with HIL** – confirmation modal before destructive actions.
- **Long‑term memory** – the bot remembers a created task across sessions.

## Known Limitations
- Rate limits on API may cause temporary failures.
- LLM fallback may produce overly verbose replies; prompt can be tuned.
- No built‑in unit tests – manual testing required for edge cases.
- Currently only supports Groq and Gemini APIs; other providers need integration.

## 📂 Repository Structure
```
.
├─ backend/            # FastAPI server
│   ├─ agents/        # Agent implementations
│   ├─ main.py
│   ├─ llm.py
│   └─ ...
├─ frontend/           # React UI
│   ├─ src/
│   │   ├─ components/
│   │   └─ App.css
│   └─ index.html
├─ .gitignore
├─ README.md
└─ package-lock.json
```

---

*Feel free to open issues or submit PRs for improvements!*
