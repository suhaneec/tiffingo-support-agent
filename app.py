"""
TiffinGo Support: the chat page for Tiffy, made with Streamlit.

Run it on your laptop:
    Mac:      .venv/bin/streamlit run app.py
    Windows:  .venv\\Scripts\\streamlit run app.py

Settings (GOOGLE_API_KEY, GEMINI_MODEL, OTP_EMAIL_ADDRESS, OTP_EMAIL_APP_PASSWORD):
- on your laptop they come from the .env file;
- online (Streamlit Community Cloud) they come from the app's Secrets.

What the page does, in order:
1. Customer log-in (email + a one-time code sent by email)  2. Chat with Tiffy,
with help topics and "My tickets" on the right, a check-in after 40 seconds of
silence, and star ratings when the chat ends.
"""

import asyncio
import os
import time
import uuid

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="TiffinGo Support", page_icon="🍱", layout="wide")

# ---- 0. Settings: .env on the laptop, Streamlit secrets online ----
SETTINGS = ("GOOGLE_API_KEY", "GEMINI_MODEL", "OTP_EMAIL_ADDRESS", "OTP_EMAIL_APP_PASSWORD")
load_dotenv()  # does nothing online, where there is no .env file
try:
    for name in SETTINGS:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
except Exception:
    pass  # no secrets file on the laptop: that's fine, .env is used instead

missing = [n for n in SETTINGS if not os.environ.get(n)]
if missing:
    st.error("This page is not set up yet. Missing setting(s): " + ", ".join(missing))
    st.stop()

# Import the agent only after the settings are in place (it reads GEMINI_MODEL).
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from support_agent import accounts  # noqa: E402
from support_agent.agent import GREETING, root_agent  # noqa: E402
from support_agent.help_docs import HELP_FILE, ensure_index, split_into_chunks  # noqa: E402
from support_agent.tickets import close_ticket, customer_tickets, save_rating, save_ticket  # noqa: E402

APP_NAME = "tiffingo_support"
IDLE_SECONDS = 40  # Tiffy checks in after this many seconds of silence
NUDGE = "Are you still there? 👀 Would you like me to connect you to an agent, or shall I close this chat?"

# FAQ groups for the "Help topics" panel. Questions not listed here go under "Other questions".
TOPICS = {
    "🛵 Orders & delivery": [
        "What areas do you deliver to?", "What are your delivery hours?", "Is there a minimum order value?",
        "How much is the delivery fee?", "How long does delivery take?", "How do I track my order?",
        "Can I schedule an order for later?",
    ],
    "💳 Payments, cancellations & refunds": [
        "Which payment methods do you accept?", "Can I cancel my order?", "How long do refunds take?",
        "How do coupons work?", "My food arrived cold or spilled. What do I do?", "An item was missing from my order.",
    ],
    "🍱 Tiffin plans": ["Do you have a monthly tiffin plan?", "Can I pause my tiffin plan?"],
    "🥗 Food & allergens": ["Is the food vegetarian?", "Do you show allergen details?", "Can I ask for less spice?"],
    "👤 Account & partners": ["How do I change my phone number?", "Can I list my home kitchen on TiffinGo?"],
}

# ---- Look and feel: orange food-delivery style (colours are in .streamlit/config.toml) ----
st.markdown(
    """
    <style>
    /* ===== Theme "Masala Sunset": warm cream page, soft abstract shapes, white cards ===== */

    /* Abstract background: soft coloured glows + a faint dot pattern, fixed behind everything */
    .stApp {
        background:
            radial-gradient(650px circle at 6% 8%, rgba(255, 154, 82, 0.30), transparent 60%),
            radial-gradient(520px circle at 96% 14%, rgba(255, 200, 87, 0.28), transparent 60%),
            radial-gradient(720px circle at 88% 96%, rgba(110, 200, 160, 0.20), transparent 60%),
            radial-gradient(560px circle at 4% 94%, rgba(242, 107, 29, 0.16), transparent 60%),
            #FFF9F3;
        background-attachment: fixed;
        isolation: isolate;
    }
    .stApp::before {
        content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
        background-image: radial-gradient(rgba(242, 107, 29, 0.13) 1.2px, transparent 1.2px);
        background-size: 24px 24px;
    }
    [data-testid="stHeader"] {background: transparent;}  /* Streamlit's top bar: see-through */

    /* Page spacing (room at the top so the title isn't hidden under Streamlit's toolbar) */
    .block-container {padding-top: 3.6rem; padding-bottom: 1.5rem; max-width: 1320px;}

    /* Orange title bar with two decorative circles */
    .tg-header {position: relative; overflow: hidden; color: white; margin-bottom: 20px;
                padding: 22px 28px; border-radius: 22px;
                background: linear-gradient(110deg, #E85A0C 0%, #F26B1D 45%, #FFA25C 100%);
                box-shadow: 0 10px 30px rgba(242, 107, 29, 0.25);}
    .tg-header::before, .tg-header::after {content: ""; position: absolute; border-radius: 50%;
                background: rgba(255, 255, 255, 0.14);}
    .tg-header::before {width: 220px; height: 220px; right: -60px; top: -90px;}
    .tg-header::after {width: 130px; height: 130px; right: 150px; bottom: -80px;}
    .tg-title {font-family: "Poppins", sans-serif; font-size: 2rem; font-weight: 800; line-height: 1.2;}
    .tg-sub {font-size: 1.02rem; opacity: 0.95; margin-top: 4px;}

    /* Big section headings */
    .tg-section {font-family: "Poppins", sans-serif; font-size: 1.45rem; font-weight: 700;
                 color: #2B2B33; margin: 4px 0 10px 0;}

    /* Small orange labels (FAQ topics) */
    .tg-label {font-size: 0.8rem; font-weight: 800; letter-spacing: 0.07em; text-transform: uppercase;
               color: #E85A0C; margin: 18px 0 4px 0;}

    /* White cards: the chat window, the right-hand panel and the login form */
    .st-key-chatbox, .st-key-sidepanel, [data-testid="stForm"] {
        background: #FFFFFF; border: 1px solid #F3E6DB !important; border-radius: 22px !important;
        box-shadow: 0 8px 28px rgba(120, 60, 20, 0.08);}
    .st-key-sidepanel {padding: 8px 18px 12px 18px;}
    [data-testid="stForm"] {padding: 22px 24px;}

    /* Login page: big welcome heading */
    .tg-hero h1 {font-family: "Poppins", sans-serif; font-size: 2.9rem; font-weight: 800;
                 line-height: 1.15; color: #2B2B33; padding: 0; margin: 10px 0 14px 0;}
    .tg-hero h1 span {color: #F26B1D;}
    .tg-hero p {font-size: 1.15rem; color: #4A4A55; line-height: 1.6; margin-bottom: 18px;}
    .tg-point {font-size: 1.05rem; color: #2B2B33; margin: 8px 0;}
    .tg-point b {color: #E85A0C;}

    /* Tabs: bigger and bolder */
    button[data-baseweb="tab"] p {font-size: 1.08rem; font-weight: 700;}

    /* Chat bubbles: Tiffy on the left in soft grey, the customer on the right in light orange */
    [data-testid="stChatMessage"] {border-radius: 18px; padding: 10px 16px; background: #F6F4F2;
                                   margin-right: 12%; gap: 10px;}
    [class*="st-key-me_"] [data-testid="stChatMessage"] {background: #FFE3CF; flex-direction: row-reverse;
                                                         margin-right: 0; margin-left: 12%;}
    [data-testid="stChatMessage"] p {font-size: 1rem; line-height: 1.55; color: #2B2B33;}

    /* FAQ list: clean rows with thin dividers instead of boxes */
    [data-testid="stExpander"] details {border: none; border-bottom: 1px solid #F0E4DA; border-radius: 0;
                                        background: transparent;}
    [data-testid="stExpander"] summary {padding: 11px 2px;}
    [data-testid="stExpander"] summary p {font-size: 1rem; font-weight: 600;}
    [data-testid="stExpander"] summary:hover p {color: #F26B1D;}
    [data-testid="stExpanderDetails"] {padding: 0 2px 12px 2px;}
    [data-testid="stExpanderDetails"] p {font-size: 0.97rem; color: #45454F; line-height: 1.6;}

    /* Ticket counters as small orange tiles */
    [data-testid="stMetric"] {background: #FFF3E9; border-radius: 16px; padding: 12px 16px;}
    </style>
    <div class="tg-header">
      <div class="tg-title">🍱 TiffinGo · Help &amp; Support</div>
      <div class="tg-sub">Chat with Tiffy · usually replies in a few seconds</div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def start_up():
    """Runs once when the app starts: build the help-docs index if it's missing, make the runner."""
    ensure_index()  # the index folder is not on GitHub, so it is built on first start
    return InMemoryRunner(agent=root_agent, app_name=APP_NAME)


@st.cache_data
def help_entries():
    """Reads the help docs (no Gemini needed) and returns a list of (title, answer) to show on the page."""
    entries = []
    for title, text in split_into_chunks(HELP_FILE.read_text(encoding="utf-8")):
        lines = text.splitlines()[1:]  # drop the "Q: ..." or "Policy: ..." line
        answer = "  \n".join(lines)
        if answer.startswith("A:"):
            answer = answer[2:].strip()
        entries.append((title, answer))
    return entries


def faq_answer(question):
    """The instant answer (with its source) for one FAQ question, straight from the help docs."""
    for title, answer in help_entries():
        if title in (question, "FAQ: " + question):
            return f"{answer}\n\n(Source: {title})"
    return None


s = st.session_state  # short name for this visitor's memory

# ---- 1. Customer log-in: email + a one-time code (OTP) ----
MAX_EMAILS = 5  # codes one visitor can ask for, so nobody can use the page to spam inboxes
WAIT_SECONDS = 30  # wait before asking for a new code


def send_otp(email):
    """Emails a fresh code and remembers only its hash. Returns an error message, or '' if it worked."""
    if s.get("otp_sends", 0) >= MAX_EMAILS:
        return "You've asked for too many codes. Please try again later."
    if time.time() - s.get("otp_sent_at", 0) < WAIT_SECONDS:
        return f"Please wait {WAIT_SECONDS} seconds before asking for a new code."
    code = accounts.new_code()
    try:
        accounts.send_code(email, code)
    except Exception as error:
        print("Could not send the login email:", error)  # shows in the terminal / Streamlit Cloud logs
        return "Sorry, we couldn't send the email right now. Please check the address and try again."
    s.update(otp_email=email, otp_hash=accounts.scramble(code), otp_tries=0,
             otp_sent_at=time.time(), otp_expires=time.time() + accounts.CODE_MINUTES * 60,
             otp_sends=s.get("otp_sends", 0) + 1)
    return ""


if not s.get("customer"):
    hero, middle = st.columns([1.15, 1], gap="large", vertical_alignment="center")
    with hero:
        # Big welcome text on the left
        st.markdown(
            """
            <div class="tg-hero">
              <h1>Hungry? Stuck?<br><span>We've got you.</span></h1>
              <p>Track orders, sort out refunds, manage your tiffin plan, and get answers in seconds
                 from Tiffy, your TiffinGo helper.</p>
              <div class="tg-point"><b>✓</b> Instant answers from our help centre</div>
              <div class="tg-point"><b>✓</b> A real person when you need one</div>
              <div class="tg-point"><b>✓</b> Your tickets stay private to you</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with middle:
        st.markdown('<div class="tg-section">Log in to get help</div>', unsafe_allow_html=True)

        if "otp_email" not in s:
            # Step 1: ask for the email and send the code.
            st.caption("We'll email you a 6-digit code. No password needed.")
            with st.form("email_form"):
                typed_email = st.text_input("Your email", placeholder="you@example.com")
                send = st.form_submit_button("Send OTP", type="primary")
            if send:
                email = accounts.clean_email(typed_email)
                problem = send_otp(email) if email else "That doesn't look like an email address."
                if problem:
                    st.error(problem)
                else:
                    st.rerun()
        else:
            # Step 2: check the code they type.
            st.success(f"We sent a 6-digit code to **{s['otp_email']}**. Check your inbox (and Spam).")
            with st.form("otp_form"):
                typed_code = st.text_input("Enter the 6-digit code", max_chars=6)
                check = st.form_submit_button("Log in", type="primary")
            if check:
                if time.time() > s["otp_expires"]:
                    st.error("This code has expired. Click Resend code to get a new one.")
                elif s["otp_tries"] >= 5:
                    st.error("Too many wrong codes. Click Resend code to get a new one.")
                elif accounts.code_matches(typed_code, s["otp_hash"]):
                    s["customer"] = s["otp_email"]
                    for key in ("otp_email", "otp_hash", "otp_tries", "otp_expires"):
                        s.pop(key, None)
                    st.rerun()
                else:
                    s["otp_tries"] += 1
                    st.error(f"That code isn't right. {5 - s['otp_tries']} tries left.")

            c1, c2 = st.columns(2)
            if c1.button("Resend code", type="tertiary"):
                problem = send_otp(s["otp_email"])
                if problem:
                    st.error(problem)
                else:
                    st.toast("New code sent!")
            if c2.button("Use a different email", type="tertiary"):
                s.pop("otp_email", None)
                st.rerun()
    st.stop()

customer = s["customer"]

# ---- 2. The chat ----
with st.spinner("Starting Tiffy (the first start can take a minute)..."):
    runner = start_up()


def new_chat():
    """Starts a fresh conversation for the logged-in customer, beginning with Tiffy's greeting."""
    s["session_id"] = str(uuid.uuid4())
    s["messages"] = [{"role": "assistant", "text": GREETING}]
    s["closed"] = False  # True once the chat has ended (then we ask for ratings)
    s["rated"] = False
    s["nudged"] = False  # True once Tiffy has checked in during this silence
    s["last_bot_time"] = time.time()
    asyncio.run(
        runner.session_service.create_session(app_name=APP_NAME, user_id=customer, session_id=s["session_id"])
    )


if "session_id" not in s:
    new_chat()


def tiffy_stream(text):
    """Sends one message to Tiffy and hands back her reply bit by bit, as Gemini writes it."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    loop = asyncio.new_event_loop()
    events = runner.run_async(
        user_id=customer,
        session_id=s["session_id"],
        new_message=message,
        run_config=RunConfig(streaming_mode=StreamingMode.SSE),  # send words as they come
    )
    shown_anything = False  # has any reply text been shown yet?
    streamed_this_step = False  # was this step's text already shown in pieces?
    try:
        while True:
            try:
                event = loop.run_until_complete(events.__anext__())
            except StopAsyncIteration:
                break
            if not (event.content and event.content.parts):
                continue
            piece = "".join(p.text or "" for p in event.content.parts if not getattr(p, "thought", False))
            if event.partial:
                # A small piece of the reply: show it straight away.
                if piece:
                    if shown_anything and not streamed_this_step:
                        yield "\n\n"
                    yield piece
                    shown_anything = streamed_this_step = True
            else:
                # The full text of one step. Show it only if it didn't arrive in pieces.
                if piece and not streamed_this_step:
                    yield ("\n\n" if shown_anything else "") + piece
                    shown_anything = True
                streamed_this_step = False
    except Exception as error:
        print("Error from the agent:", error)  # shows in the terminal / Streamlit Cloud logs
        if "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error):
            yield "Sorry, I'm getting too many messages right now. Please try again in a minute."
        else:
            yield "Sorry, something went wrong. Please try again."
        shown_anything = True
    finally:
        loop.run_until_complete(events.aclose())
        loop.close()
    if not shown_anything:
        yield "Sorry, I have no reply right now."


def bot_says(text):
    """Adds a message from Tiffy to the chat."""
    s["messages"].append({"role": "assistant", "text": text})
    s["last_bot_time"] = time.time()


def ask(question, instant_answer=None):
    """Button helper: queue a message to send (with an instant answer if we already know it)."""
    s["pending"] = (question, instant_answer)


def connect_agent():
    """Raises a ticket straight away (no Gemini call) so a person takes over."""
    said = [m["text"] for m in s["messages"] if m["role"] == "user"]
    summary = said[-1] if said else "Customer asked to talk to an agent."
    s["messages"].append({"role": "user", "text": "Connect me to an agent, please."})
    ticket_id = save_ticket(customer, summary, "asked for a person")
    bot_says(f"Done! I've raised ticket **{ticket_id}**. A person from our team will reply within 24 hours. 🙏")


def close_chat():
    s["closed"] = True


def log_out():
    for key in ("customer", "session_id", "messages", "pending"):
        s.pop(key, None)


left, right = st.columns([3, 2], gap="large")

# ---- Left side: the chat window ----
with left:
    top_left, top_right = st.columns([3, 2], vertical_alignment="center")
    top_left.markdown('<div class="tg-section">💬 Chat with Tiffy</div>', unsafe_allow_html=True)
    top_left.caption(f"Logged in as {customer[0]}•••@{customer.split('@')[1]}")
    with top_right:
        b1, b2 = st.columns(2)
        b1.button("End chat", on_click=close_chat, disabled=s["closed"], type="tertiary", width="stretch")
        b2.button("Log out", on_click=log_out, type="tertiary", width="stretch")

    # ---- Quick-help buttons, above the chat like suggestion chips ----
    if not s["closed"]:
        q1, q2, q3, q4 = st.columns(4)
        q1.button("📦 Track order", on_click=ask, args=("I want to track my order.",), width="stretch")
        q2.button("💸 Refund / cancel", on_click=ask, args=("I want to cancel my order or get a refund.",),
                  width="stretch")
        q3.button("🕒 Delivery hours", on_click=ask,
                  args=("What are your delivery hours?", faq_answer("What are your delivery hours?")),
                  width="stretch")
        q4.button("👩‍💼 Talk to agent", on_click=connect_agent, width="stretch")

    def bubble(role, key):
        """One chat bubble. The customer's bubbles get a key starting with "me_" so the style puts them on the right."""
        with st.container(key=("me_" if role == "user" else "bot_") + str(key)):
            return st.chat_message(role, avatar="🍱" if role == "assistant" else "🙂")

    chat_box = st.container(height=420, key="chatbox")  # "chatbox" gets the white card style
    with chat_box:
        for i, m in enumerate(s["messages"]):
            with bubble(m["role"], i):
                st.markdown(m["text"])
        # After the 40-second check-in, offer the two choices as buttons.
        if not s["closed"] and s["messages"][-1]["text"] == NUDGE:
            c1, c2 = st.columns(2)
            c1.button("👩‍💼 Connect me to an agent", on_click=connect_agent, width="stretch")
            c2.button("✅ Close chat", on_click=close_chat, width="stretch")

    if s["closed"]:
        # ---- Ratings when the chat has ended ----
        if not s["rated"]:
            st.markdown("#### Chat ended. How did we do?")
            st.write("How was your chat with Tiffy?")
            chat_stars = st.feedback("stars", key=f"chat_stars_{s['session_id']}")
            st.write("Was your problem solved?")
            solved_stars = st.feedback("stars", key=f"solved_stars_{s['session_id']}")
            comment = st.text_area("Anything else you'd like to tell us? (optional)")
            if st.button("Submit rating", type="primary"):
                if chat_stars is None or solved_stars is None:
                    st.warning("Please pick stars for both questions.")
                else:
                    save_rating(customer, chat_stars + 1, solved_stars + 1, comment)  # stars come as 0-4
                    s["rated"] = True
                    st.rerun()
        else:
            st.success("Thank you for your rating! 🧡")
        st.button("Start a new chat", type="primary", on_click=new_chat)
    else:
        # ---- The message box, right under the chat ----
        typed = st.chat_input("Type your message to Tiffy...")
        question, instant_answer = (typed, None) if typed else s.pop("pending", (None, None))

        if question:
            s["messages"].append({"role": "user", "text": question})
            s["nudged"] = False  # the customer spoke, so Tiffy may check in again after the next silence
            n = len(s["messages"])
            with chat_box:
                with bubble("user", n):
                    st.markdown(question)
                with bubble("assistant", n + 1):
                    if instant_answer:
                        st.markdown(instant_answer)  # straight from the help docs, no waiting
                        answer = instant_answer
                    else:
                        with st.spinner("Tiffy is typing..."):
                            answer = st.write_stream(tiffy_stream(question))
            bot_says(answer)

        # ---- The 40-second check-in (runs quietly every 5 seconds, uses no Gemini) ----
        @st.fragment(run_every=5)
        def idle_check():
            customer_has_spoken = any(m["role"] == "user" for m in s["messages"])
            waiting_for_customer = s["messages"][-1]["role"] == "assistant"
            if customer_has_spoken and waiting_for_customer and not s["nudged"] and not s["closed"]:
                if time.time() - s["last_bot_time"] >= IDLE_SECONDS:
                    bot_says(NUDGE)
                    s["nudged"] = True
                    st.rerun()

        idle_check()

# ---- Right side: help topics and the customer's own tickets (drawn last, so new tickets show) ----
with right, st.container(key="sidepanel"):  # "sidepanel" gets the white card style
    help_tab, tickets_tab = st.tabs(["❓ Help topics", "🎫 My tickets"])

    with help_tab:
        with st.container(height=560, border=False):
            entries = help_entries()
            faqs = {t[len("FAQ: "):]: a for t, a in entries if t.startswith("FAQ: ")}
            policies = [(t, a) for t, a in entries if not t.startswith("FAQ: ")]
            listed = {q for qs in TOPICS.values() for q in qs}
            groups = dict(TOPICS)
            others = [q for q in faqs if q not in listed]
            if others:
                groups["💬 Other questions"] = others

            for topic, questions in groups.items():
                st.markdown(f'<div class="tg-label">{topic}</div>', unsafe_allow_html=True)
                for q in questions:
                    if q in faqs:
                        with st.expander(q):
                            st.markdown(faqs[q])
                            st.button("Ask Tiffy →", key=f"faq_{q}", on_click=ask, type="tertiary",
                                      args=(q, faq_answer(q)), disabled=s["closed"])
            st.markdown('<div class="tg-label">📜 Policies</div>', unsafe_allow_html=True)
            for title, text in policies:
                with st.expander(title):
                    st.markdown(text)

    with tickets_tab:
        tickets = customer_tickets(customer)  # only this customer's tickets, never anyone else's
        open_count = sum(1 for t in tickets if t["status"] == "open")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total", len(tickets))
        m2.metric("Open", open_count)
        m3.metric("Closed", len(tickets) - open_count)

        if not tickets:
            st.caption("You have no tickets yet. If Tiffy hands you over to a person, your ticket shows here.")
        for t in tickets:
            with st.container(border=True):
                status = "🟠 Open" if t["status"] == "open" else "✅ Closed"
                flag = "🔴 High priority" if t["priority"] == "high" else "Normal priority"
                st.markdown(f"**{t['ticket_id']}** · {status} · {flag}  \n"
                            f"**{t['reason'].capitalize()}**  \n_{t['message']}_  \n{t['time']}")
                if t["status"] == "open":
                    st.button("Mark as resolved", key=f"close_{t['ticket_id']}",
                              on_click=close_ticket, args=(t["ticket_id"], customer))
