# Snapdeal AI Virtual KAM (voice-first)

A seller talks to "Priya", an AI Key Account Manager. She reads the seller's numbers first, asks follow-up questions, recommends 2-3 actions and summarises the call. Voice in and voice out, free to run.

## Structure
```
snapdeal-kam/
├── frontend/              # static UI (served by the backend)
│   ├── index.html
│   ├── css/style.css
│   └── js/  app.js (screens + call flow) · voice.js (mic + speaker) · api.js (backend calls)
├── backend/               # FastAPI
│   ├── main.py            # routes: /api/sample /api/upload /api/chat /api/summary
│   ├── data_loader.py     # CSV / Excel / JSON / PDF parsing + sample dataset
│   └── analyzer.py        # finds what changed, ranks issues, recommendations
├── ai/                    # everything LLM-related
│   ├── gemini_client.py   # Gemini REST call
│   ├── prompts.py         # system / summary / PDF-extraction prompts
│   ├── kam_agent.py       # Gemini first, offline fallback
│   └── offline_engine.py  # scripted KAM when no key or quota hit
├── venv/                  # you create this (step 1)
├── requirements.txt
└── .env                   # you create this (step 3)
```

## Run
```bash
# 1. virtual environment (from the project root)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. free Gemini key: https://aistudio.google.com/app/apikey
# 3. config
cp .env.example .env              # then paste your key, set GEMINI_MODEL to your model ID

# 4. start
uvicorn backend.main:app --reload
```
Open **http://localhost:8000** in Chrome or Edge and allow the microphone.

## Workflow
1. Front page: upload CSV/Excel/JSON/PDF, or click **Use sample dataset**.
2. Backend parses it into prev vs current metrics and diagnoses it (stock-outs, cancellations, price, views, margin, returns).
3. Voice call: browser speech-to-text -> `/api/chat` -> Gemini (with the data in its prompt) -> browser text-to-speech.
4. End of call: `/api/summary` returns key issues, actions and next steps (shown and spoken).

## Notes
- Speech uses the browser's free Web Speech API (no paid STT/TTS). Chrome/Edge only.
- The Gemini key stays on the server (`.env`), never in the browser.
- No key or quota exceeded: the bot automatically switches to the offline scripted mode.
- Sample data = the assignment table, plus **assumed** profit, margin, views and listings (flagged in the UI).
- Messy PDFs: if the regex parser fails, Gemini extracts the numbers.


Final Deployment for testing Purpose only : https://snapdeal-kam-mh3r.onrender.com/
