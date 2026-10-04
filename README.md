# Counselling Practice App 

A web app where trainee counsellors practise with LLM-simulated clients and get supervisor-style
feedback.

Note: I used streamlit to build the app and rewrote the script for making OpenAI/Gemini API calls since the original references the degenerated `google-generativeai` package.

Stack: Streamlit + SQLite + Gemini/OpenAI
## Features

| Feature | Where |
|---|---|
| Login / register (passwords salted and hashed[PBKDF2]) | `page_auth` in `app.py`, `users` table |
| Home with access to real and simulated patients | `page_home` |
| New simulated patient: gender, age group, ethnicity, concerns. LLM builds a full persona | `page_new_patient`, `prompts.persona_request` |
| Existing patients: list of clients you've seen, with summaries of previous sessions | `page_existing` |
| Session page: turn-by-turn chat[*client speaks first*] | `page_session` |
| Session memory: structured notes saved at the end of each session and fed into the next. Data saved in databse via SQlite3 | `prompts.summary_request`, `sessions.summary` |
| **Feedback**: 7 skills scored 1–5 with quoted evidence, overall score, strengths, and suggestions | `page_feedback`, `prompts.feedback_request` |
| Model selector: Gemini / OpenAI / Offline demo | sidebar, `llm.py` |
| Real patients | Currently a placeholder page |

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
# edit .env.example to contain your Gemini or OpenAI key and change the name .env
python -m streamlit run app.py
```

You can choose 'Offline Demo' to run without an OpenAI or Gemini API key, but the responses will be non-interactive sample text

## Files

```
app.py        Streamlit UI: pages and navigation
db.py         SQLite schema and handler
llm.py        Interface for API calls 
prompts.py    Persona, Session notes and Feedback
```

## Usage Notes

- Default Gemini model is `gemini-3.5-flash`. 
- `counseling.db` File is created upon running app.py and stores persona/session/feedback info. Add/change a env DP_PATH variable if you want to refer to a specific counseling.db file of your own[formats must change]
- Passwords are salted and hashed before being put in `counseling.db`, so store your dummy log-in info on your own machine if you  don't want to lose it
- I noticed that the summary/feedback generator can sometimes focus on input from the user and mistake the user's sentiments for that of the simulated client. Keep inputs emotionally neutral.