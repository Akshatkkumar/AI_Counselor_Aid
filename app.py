
import os
from statistics import mean

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import db  
from llm import GEMINI_MODELS, LLM, OPENAI_MODELS 
from prompts import *

st.set_page_config(page_title="Counselling Practice", page_icon="🧑‍⚕️", layout="centered")
db.init_db()

ss = st.session_state
ss.setdefault("page", "auth")
ss.setdefault("user", None)

COUNSELOR_AVATAR, PATIENT_AVATAR = "🧑‍⚕️", "🧑"


def go(page: str, **state):
    ss.update(state)
    ss.page = page
    st.rerun()


# sidebar: model choice

def sidebar():
    with st.sidebar:
        st.markdown(f"**Signed in as** {ss.user['username']}")
        c1, c2 = st.columns(2)
        if c1.button("🏠 Home", use_container_width=True):
            go("home")
        if c2.button("Log out", use_container_width=True):
            ss.clear()
            st.rerun()

        st.divider()
        st.subheader("Model")
        provider = st.selectbox("Provider", ["Gemini", "OpenAI", "Offline demo"], key="provider",
                                help="Offline demo returns canned text so you can try the flow without a key.")
        if provider == "Offline demo":
            ss.model = "offline"
            return
        default = os.getenv("GEMINI_MODEL" if provider == "Gemini" else "OPENAI_MODEL")
        options = list(dict.fromkeys(([default] if default else []) +
                                     (GEMINI_MODELS if provider == "Gemini" else OPENAI_MODELS)))
        choice = st.selectbox("Model", options + ["Custom…"], key=f"model_{provider}")
        ss.model = st.text_input("Custom model name", key=f"custom_{provider}") if choice == "Custom…" else choice

        env_key = "GEMINI_API_KEY" if provider == "Gemini" else "OPENAI_API_KEY"
        if not os.getenv(env_key):
            st.text_input(f"{provider} API key", type="password", key=f"key_{provider}",
                          help=f"Or set {env_key} in a .env file.")


def llm():
    provider = ss.get("provider", "Gemini")
    return LLM(provider, ss.get("model") or GEMINI_MODELS[0], ss.get(f"key_{provider}") or None)

# page: login / register

def page_auth():
    st.title("🧑‍⚕️ Counselling Practice")
    st.caption("Practise your counselling skills with simulated clients and get supervisor-style feedback.")
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab, st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            user = db.authenticate(username, password)
            if user:
                go("home", user=user)
            st.error("Incorrect username or password.")

    with register_tab, st.form("register"):
        username = st.text_input("Choose a username")
        password = st.text_input("Choose a password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Create account", type="primary"):
            if len(username.strip()) < 3:
                st.error("Username must be at least 3 characters.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            elif password != confirm:
                st.error("Passwords don't match.")
            else:
                uid = db.create_user(username, password)
                if uid is None:
                    st.error("That username is taken.")
                else:
                    go("home", user={"id": uid, "username": username.strip().lower()})


# page: home

def page_home():
    st.title(f"Welcome, {ss.user['username']}")
    st.write("Who would you like to practise with today?")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("Real patients")
        st.caption("Practise with de-identified real case material.")
        if st.button("Real patients", use_container_width=True):
            go("real")
    with c2.container(border=True):
        st.subheader("Simulated patients")
        st.caption("AI-simulated clients you design or have met before.")
        if st.button("Simulated patients", type="primary", use_container_width=True):
            go("sim_menu")


def page_real():
    st.title("Real patients")
    st.info(
        "This module is not available yet. Using real patient material requires de-identified, consented "
        "case records and approval from your programme's ethics process. Once such cases are available, "
        "they can be loaded as patient profiles and used with the same session and feedback flow."
    )
    if st.button("← Back"):
        go("home")


def page_sim_menu():
    st.title("Simulated patients")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.subheader("New patient")
        st.caption("Choose gender, age group, ethnicity and concerns.")
        if st.button("Create a new patient", type="primary", use_container_width=True):
            go("new_patient")
    with c2.container(border=True):
        st.subheader("Existing patients")
        st.caption("Continue with a client you've spoken to before.")
        if st.button("Choose an existing patient", use_container_width=True):
            go("existing")


# page: new patient

def page_new_patient():
    st.title("New simulated patient")
    with st.form("new_patient"):
        c1, c2, c3 = st.columns(3)
        gender = c1.selectbox("Gender", GENDERS)
        age_group = c2.selectbox("Age group", AGE_GROUPS, index=1)
        ethnicity = c3.selectbox("Ethnicity", ETHNICITIES)
        concerns = st.multiselect("Mental health concerns", CONCERNS, default=["Academic performance"],
                                  max_selections=4)
        notes = st.text_area("Anything else? (optional)",
                             placeholder="e.g. recently moved from overseas, very reluctant to talk")
        submitted = st.form_submit_button("Start the session", type="primary")

    if st.button("← Back"):
        go("sim_menu")

    if submitted:
        if not concerns:
            st.error("Pick at least one concern.")
            return
        try:
            with st.spinner("Creating your client…"):
                persona = llm().json(PERSONA_SYSTEM, persona_request(gender, age_group, ethnicity, concerns, notes))
            if not persona.get("name"):
                raise RuntimeError("The model returned an incomplete profile. Try again.")
            try:
                persona["age"] = int(persona.get("age"))
            except (TypeError, ValueError):
                persona["age"] = None
        except RuntimeError as e:
            st.error(str(e))
            return
        pid = db.create_patient(ss.user["id"], gender, age_group, ethnicity, concerns, persona)
        go("session", session_id=db.get_or_create_open_session(ss.user["id"], pid))


# page: existing patients

def render_summary(s):
    st.markdown(f"**{s.get('one_line_summary', '')}**")
    fields = [("Concerns", "presenting_concerns"), ("Disclosed", "key_disclosures"),
              ("People", "important_people"), ("Next steps", "agreed_next_steps"),
              ("Risk", "risk_indicators"), ("Still to explore", "unexplored_topics")]
    for label, key in fields:
        val = s.get(key)
        if val:
            st.markdown(f"- *{label}:* {', '.join(val) if isinstance(val, list) else val}")
    if s.get("emotional_state_start") or s.get("emotional_state_end"):
        st.markdown(f"- *Mood:* {s.get('emotional_state_start', '?')} → {s.get('emotional_state_end', '?')}")
    if s.get("progress_made"):
        st.markdown(f"- *Progress:* {s['progress_made']}")
    if s.get("rapport"):
        st.markdown(f"- *Rapport:* {s['rapport']}")


def overall_score(feedback):
    scores = [v.get("score") for v in feedback.get("scores", {}).values() if isinstance(v.get("score"), (int, float))]
    return round(mean(scores), 1) if scores else None


def page_existing():
    st.title("Existing patients")
    if st.button("← Back"):
        go("sim_menu")
    patients = db.list_patients(ss.user["id"])
    if not patients:
        st.info("You haven't created any simulated patients yet.")
        if st.button("Create one", type="primary"):
            go("new_patient")
        return

    for p in patients:
        sessions = db.list_sessions(p["id"])
        done = [s for s in sessions if s["ended_at"]]
        is_open = any(not s["ended_at"] for s in sessions)
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.subheader(p["name"])
            c1.caption(f"{p['age'] or p['age_group']} · {p['gender']} · {p['ethnicity']} · "
                       f"{p['persona'].get('occupation', '')}")
            c1.write("Concerns: " + ", ".join(p["concerns"]))
            label = "Resume session" if is_open else "Start session"
            if c2.button(label, key=f"start_{p['id']}", type="primary", use_container_width=True):
                go("session", session_id=db.get_or_create_open_session(ss.user["id"], p["id"]))
            c2.caption(f"{len(done)} completed session{'s' if len(done) != 1 else ''}")

            if done:
                with st.expander("What was discussed in previous sessions"):
                    for i, s in enumerate(done, 1):
                        score = overall_score(s["feedback"]) if s["feedback"] else None
                        st.markdown(f"##### Session {i} · {s['started_at'][:10]}"
                                    + (f" · score {score}/5" if score else ""))
                        if s["summary"]:
                            render_summary(s["summary"])
                        else:
                            st.caption("No summary recorded.")
                        if st.button("View feedback", key=f"fb_{s['id']}"):
                            go("feedback", session_id=s["id"])


# page: counselling session

def page_session():
    sid = ss.get("session_id")
    session = db.get_session(sid) if sid else None
    if not session:
        go("sim_menu")
    patient = db.get_patient(session["patient_id"])
    persona = patient["persona"]
    n = db.session_number(sid)
    past = [s["summary"] for s in db.list_sessions(patient["id"], completed_only=True)
            if s["summary"] and s["id"] < sid]
    system = patient_system_prompt(patient, past, n)
    cue = OPENING_CUE_RETURNING if past else OPENING_CUE_FIRST
    ended = session["ended_at"] is not None

    # profile summary
    with st.container(border=True):
        st.subheader(f"{persona.get('name')} · Session {n}")
        st.caption(f"{persona.get('age') or patient['age_group']} · {patient['gender']} · {patient['ethnicity']} · "
                   f"{persona.get('occupation', '')}")
        st.write("**Concerns:** " + ", ".join(patient["concerns"]))
        st.write(f"**Referral note:** {persona.get('presenting_problem', '')}")
        if past:
            with st.expander("Notes from previous sessions"):
                for i, s in enumerate(past, 1):
                    st.markdown(f"**Session {i}**")
                    render_summary(s)

    messages = db.get_messages(sid)

    def patient_reply():
        try:
            with st.spinner(f"{persona.get('name', 'Client')} is responding…"):
                reply = llm().chat(system, to_llm_turns(db.get_messages(sid), cue))
            db.add_message(sid, "patient", reply)
            st.rerun()
        except RuntimeError as e:
            st.error(str(e))

    if not messages and not ended:
        patient_reply()

    for m in messages:
        if m["role"] == "patient":
            st.chat_message(persona.get("name", "Client"), avatar=PATIENT_AVATAR).write(m["content"])
        else:
            st.chat_message("You", avatar=COUNSELOR_AVATAR).write(m["content"])

    if ended:
        st.success("This session has ended.")
        if session["summary"]:
            with st.expander("Session notes (saved for next time)", expanded=True):
                render_summary(session["summary"])
        c1, c2 = st.columns(2)
        if c1.button("Feedback on the counselling session", type="primary", use_container_width=True):
            go("feedback")
        if c2.button("Back to patients", use_container_width=True):
            go("existing")
        return

    if messages and messages[-1]["role"] == "counselor":
        if st.button("Retry client reply"):
            patient_reply()

    counselor_turns = sum(m["role"] == "counselor" for m in messages)
    if st.button("End session", disabled=counselor_turns == 0,
                 help="Ends the session, saves notes for next time, and unlocks feedback."):
        try:
            with st.spinner("Writing session notes…"):
                summary = llm().json(SUMMARY_SYSTEM, summary_request(patient, transcript(messages, persona.get("name"))))
        except RuntimeError as e:
            st.error(f"Couldn't summarise the session: {e}")
            return
        db.end_session(sid, summary)
        st.rerun()

    if text := st.chat_input("Your response as the counsellor…"):
        db.add_message(sid, "counselor", text.strip())
        st.chat_message("You", avatar=COUNSELOR_AVATAR).write(text)
        patient_reply()


# page: feedback

def page_feedback():
    sid = ss.get("session_id")
    session = db.get_session(sid) if sid else None
    if not session:
        go("existing")
    patient = db.get_patient(session["patient_id"])
    messages = db.get_messages(sid)
    name = patient["persona"].get("name", "Client")

    st.title("Session feedback")
    st.caption(f"{name} · Session {db.session_number(sid)} · {session['started_at'][:10]}")

    feedback = session["feedback"]
    if not feedback or st.button("Regenerate feedback"):
        try:
            with st.spinner("Your supervisor is reviewing the session…"):
                feedback = llm().json(FEEDBACK_SYSTEM, feedback_request(patient, transcript(messages, name)), 0.2)
            db.save_feedback(sid, feedback)
        except RuntimeError as e:
            st.error(str(e))
            return

    overall = overall_score(feedback)
    st.metric("Overall score", f"{overall} / 5" if overall else "–",
              help="Average of the dimension scores below.")

    st.subheader("Skills")
    scores = feedback.get("scores", {})
    for key, (label, anchor) in FEEDBACK_DIMENSIONS.items():
        item = scores.get(key, {})
        score = item.get("score")
        if not isinstance(score, (int, float)):
            continue
        st.progress(min(max(score / 5, 0), 1), text=f"**{label}** — {score}/5")
        with st.expander("Why this score", expanded=False):
            st.caption(anchor)
            if item.get("evidence"):
                st.markdown(f"> {item['evidence']}")
            st.write(item.get("comment", ""))

    if feedback.get("strengths"):
        st.subheader("What went well")
        for s in feedback["strengths"]:
            st.markdown(f"- {s}")

    if feedback.get("improvements"):
        st.subheader("How to improve")
        for imp in feedback["improvements"]:
            with st.container(border=True):
                st.markdown(f"**{imp.get('issue', '')}**")
                if imp.get("original"):
                    st.markdown(f"You said: *“{imp['original']}”*")
                if imp.get("better"):
                    st.markdown(f"Try: *“{imp['better']}”*")

    if feedback.get("overall_comment"):
        st.subheader("Supervisor's comments")
        st.write(feedback["overall_comment"])

    with st.expander("Full transcript"):
        st.text(transcript(messages, name))

    c1, c2 = st.columns(2)
    if c1.button("Back to session", use_container_width=True):
        go("session")
    if c2.button("Back to patients", use_container_width=True):
        go("existing")


# router

PAGES = {
    "home": page_home, "real": page_real, "sim_menu": page_sim_menu, "new_patient": page_new_patient,
    "existing": page_existing, "session": page_session, "feedback": page_feedback,
}

if not ss.user:
    page_auth()
else:
    sidebar()
    PAGES.get(ss.page, page_home)()
