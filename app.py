"""
TiffinGo Support: the chat page for Tiffy, made with Streamlit.

Run it on your laptop:
    Mac:      .venv/bin/streamlit run app.py
    Windows:  .venv\\Scripts\\streamlit run app.py

Settings (GOOGLE_API_KEY, GEMINI_MODEL, APP_PASSCODE):
- on your laptop they come from the .env file;
- online (Streamlit Community Cloud) they come from the app's Secrets.
"""

import asyncio
import hmac
import os
import uuid

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="TiffinGo Support", page_icon="🍱")

# ---- 0. Settings: .env on the laptop, Streamlit secrets online ----
load_dotenv()  # does nothing online, where there is no .env file
try:
    for name in ("GOOGLE_API_KEY", "GEMINI_MODEL", "APP_PASSCODE"):
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
except Exception:
    pass  # no secrets file on the laptop: that's fine, .env is used instead

missing = [n for n in ("GOOGLE_API_KEY", "GEMINI_MODEL", "APP_PASSCODE") if not os.environ.get(n)]
if missing:
    st.error("This page is not set up yet. Missing setting(s): " + ", ".join(missing))
    st.stop()

# Import the agent only after the settings are in place (it reads GEMINI_MODEL).
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from support_agent.agent import GREETING, root_agent  # noqa: E402
from support_agent.help_docs import ensure_index  # noqa: E402
from support_agent.tickets import open_tickets  # noqa: E402

APP_NAME = "tiffingo_support"

st.title("🍱 TiffinGo Support")


@st.cache_resource
def start_up():
    """Runs once when the app starts: build the help-docs index if it's missing, make the runner."""
    ensure_index()  # the index folder is not on GitHub, so it is built on first start
    return InMemoryRunner(agent=root_agent, app_name=APP_NAME)


# ---- 1. Passcode: the chat opens only after the right passcode ----
if not st.session_state.get("unlocked"):
    entered = st.text_input("Enter the passcode to start chatting", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), os.environ["APP_PASSCODE"].encode()):
            st.session_state["unlocked"] = True
            st.rerun()
        else:
            st.error("That passcode is not right.")
    st.stop()

# ---- 2. The chat ----
with st.spinner("Starting Tiffy (the first start can take a minute)..."):
    runner = start_up()

# One conversation per browser visit, starting with Tiffy's greeting.
if "session_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["messages"] = [{"role": "assistant", "text": GREETING}]
    asyncio.run(
        runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=st.session_state["user_id"],
            session_id=st.session_state["session_id"],
        )
    )


async def ask_tiffy(text):
    """Send one customer message to Tiffy and return her final reply."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    async for event in runner.run_async(
        user_id=st.session_state["user_id"],
        session_id=st.session_state["session_id"],
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            reply = "".join(p.text or "" for p in event.content.parts)
    return reply


# Show the conversation so far (chat bubbles).
for m in st.session_state["messages"]:
    with st.chat_message(m["role"], avatar="🍱" if m["role"] == "assistant" else None):
        st.markdown(m["text"])

# Take a new message, send it to Tiffy and show the reply.
if question := st.chat_input("Ask Tiffy about orders, delivery, plans or refunds"):
    st.session_state["messages"].append({"role": "user", "text": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="🍱"):
        with st.spinner("Tiffy is typing..."):
            try:
                answer = asyncio.run(ask_tiffy(question))
            except Exception as error:
                if "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error):
                    answer = "Sorry, I'm getting too many messages right now. Please try again in a minute."
                else:
                    answer = "Sorry, something went wrong. Please try again."
                print("Error from the agent:", error)  # shows in the terminal / Streamlit Cloud logs
        answer = answer or "Sorry, I have no reply right now."
        st.markdown(answer)
    st.session_state["messages"].append({"role": "assistant", "text": answer})

# ---- 3. Sidebar: open tickets (drawn last, so a ticket made just now shows up) ----
with st.sidebar:
    st.header("Open tickets")
    tickets = open_tickets()
    if not tickets:
        st.caption("No open tickets yet.")
    for t in tickets:
        flag = "🔴 HIGH" if t["priority"] == "high" else "🟢 normal"
        st.markdown(f"**{t['ticket_id']}** · {flag}  \n{t['reason']}  \n_{t['message']}_  \n{t['time']}")
        st.divider()
