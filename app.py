"""
TiffinGo Support: the Help Centre page with Tiffy, made with Streamlit.

Run it on your laptop:
    Mac:      .venv/bin/streamlit run app.py
    Windows:  .venv\\Scripts\\streamlit run app.py

Settings (GOOGLE_API_KEY, GEMINI_MODEL, OTP_EMAIL_ADDRESS, OTP_EMAIL_APP_PASSWORD):
- on your laptop they come from the .env file;
- online (Streamlit Community Cloud) they come from the app's Secrets.

What the page does, in order:
1. Customer log-in (email + a one-time code sent by email)
2. Chat with Tiffy (big chat panel), with the help centre and "My tickets" on the right,
   a check-in after 40 seconds of silence, and star ratings when the chat ends.
"""

import asyncio
import html
import os
import time
import uuid
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="TiffinGo Help Centre", page_icon="🍱", layout="wide")

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
NUDGE = "Are you still there? Would you like me to connect you to an agent, or shall I close this chat?"

# Icons (Google's clean "material" line icons instead of emojis)
TIFFY_AVATAR = ":material/support_agent:"
CUSTOMER_AVATAR = ":material/person:"

# FAQ groups for the help centre. Questions not listed here go under "Other questions".
TOPICS = {
    "Orders & delivery": [
        "What areas do you deliver to?", "What are your delivery hours?", "Is there a minimum order value?",
        "How much is the delivery fee?", "How long does delivery take?", "How do I track my order?",
        "Can I schedule an order for later?",
    ],
    "Payments, cancellations & refunds": [
        "Which payment methods do you accept?", "Can I cancel my order?", "How long do refunds take?",
        "How do coupons work?", "My food arrived cold or spilled. What do I do?", "An item was missing from my order.",
    ],
    "Tiffin plans": ["Do you have a monthly tiffin plan?", "Can I pause my tiffin plan?"],
    "Food & allergens": ["Is the food vegetarian?", "Do you show allergen details?", "Can I ask for less spice?"],
    "Account & partners": ["How do I change my phone number?", "Can I list my home kitchen on TiffinGo?"],
}

# The TiffinGo logo: an orange rounded square with a white three-tier tiffin box (drawn as SVG).
LOGO = """
<svg width="38" height="38" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg">
  <rect width="38" height="38" rx="11" fill="#F26B1D"/>
  <path d="M14 12V9.5a2.5 2.5 0 0 1 2.5-2.5h5a2.5 2.5 0 0 1 2.5 2.5V12" fill="none" stroke="#fff" stroke-width="2.2"/>
  <rect x="9.5" y="12" width="19" height="6.5" rx="2.4" fill="#fff"/>
  <rect x="9.5" y="20" width="19" height="6.5" rx="2.4" fill="#fff" opacity="0.88"/>
  <rect x="9.5" y="28" width="19" height="4" rx="2" fill="#fff" opacity="0.72"/>
</svg>
"""

# Background: a few thin, flowing orange lines (an SVG picture placed behind the whole page).
LINES = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
  <g fill="none" stroke="#F26B1D" stroke-width="1.4">
    <path d="M-60 640 C 300 500, 620 780, 940 600 S 1380 420, 1520 520" stroke-opacity="0.22"/>
    <path d="M-60 690 C 320 560, 640 840, 960 650 S 1400 470, 1520 580" stroke-opacity="0.14"/>
    <path d="M-60 745 C 340 620, 660 900, 980 705 S 1420 530, 1520 645" stroke-opacity="0.08"/>
    <path d="M880 -30 C 1040 110, 1240 50, 1520 190" stroke-opacity="0.16"/>
    <path d="M940 -30 C 1100 150, 1300 100, 1520 255" stroke-opacity="0.09"/>
  </g>
</svg>
"""
LINES_URL = "data:image/svg+xml;utf8," + quote(" ".join(LINES.split()))

# ---- Look and feel (colours and fonts are in .streamlit/config.toml) ----
st.markdown(
    f"""
    <style>
    /* Background: thin orange lines + soft warm glows, fixed so they stay put when you scroll.
       It goes on Streamlit's page area itself, so nothing paints over it. */
    .stApp, [data-testid="stAppViewContainer"] {{
        background:
            url("{LINES_URL}") center / cover no-repeat fixed,
            radial-gradient(900px circle at 0% 0%, rgba(255, 160, 100, 0.16), transparent 60%) fixed,
            radial-gradient(800px circle at 100% 100%, rgba(255, 196, 120, 0.14), transparent 60%) fixed,
            #FBF8F5 !important;
    }}
    [data-testid="stMain"], [data-testid="stMainBlockContainer"] {{background: transparent !important;}}
    header[data-testid="stHeader"] {{display: none;}}  /* hide Streamlit's own top bar */

    /* Full width, with room for the fixed top bar */
    .block-container {{max-width: 100%; padding: 88px 2rem 1rem 2rem;}}

    /* Fixed top bar with the logo and app name: it never scrolls away */
    .tg-nav {{position: fixed; top: 0; left: 0; right: 0; height: 66px; z-index: 1000;
             display: flex; align-items: center; justify-content: space-between; padding: 0 2rem;
             background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(8px);
             border-bottom: 1px solid #EFE7E0; box-shadow: 0 2px 14px rgba(40, 20, 0, 0.05);}}
    .tg-brand {{display: flex; align-items: center; gap: 12px;}}
    .tg-word {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.45rem; font-weight: 800;
              color: #1E1E28; letter-spacing: -0.02em;}}
    .tg-divider {{width: 1px; height: 24px; background: #E2D9D1;}}
    .tg-area {{font-size: 1.02rem; font-weight: 600; color: #6B6B76;}}
    .tg-nav-right {{font-size: 0.9rem; color: #6B6B76;}}
    .tg-nav-right b {{color: #1E1E28;}}

    /* Page headings */
    .tg-h1 {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.85rem; font-weight: 800;
            color: #1E1E28; letter-spacing: -0.02em; margin: 0;}}
    .tg-lead {{font-size: 1.02rem; color: #6B6B76; margin: 2px 0 0 0;}}
    .tg-label {{font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
               color: #9A6A4A; margin: 18px 0 4px 0;}}

    /* White cards: the chat panel and the help centre panel */
    .st-key-chatcard, .st-key-sidepanel {{
        background: #FFFFFF; border: 1px solid #EFE7E0 !important; border-radius: 18px !important;
        box-shadow: 0 6px 24px rgba(40, 20, 0, 0.06);}}
    .st-key-chatcard {{padding: 0 0 14px 0; gap: 0.6rem;}}
    .st-key-sidepanel {{padding: 6px 20px 14px 20px;}}

    /* Chat panel header strip */
    .tg-chat-head {{display: flex; align-items: center; gap: 12px; padding: 14px 0;}}
    .tg-chat-name {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.1rem; font-weight: 700; color: #1E1E28;}}
    .tg-chat-status {{font-size: 0.86rem; color: #6B6B76;}}
    .tg-dot {{display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #22A35A;
             margin-right: 6px; vertical-align: middle;}}
    .st-key-chatcard > div:not(.st-key-chathead) {{padding-left: 20px; padding-right: 20px;}}
    .st-key-chathead {{padding: 0 20px !important; border-bottom: 1px solid #F1EAE4;}}

    /* The chat messages area: tall, fills the screen, never scrolls sideways */
    .st-key-chatbox {{height: calc(100vh - 330px) !important; min-height: 380px; overflow-x: hidden !important;}}

    /* Chat bubbles: Tiffy on the left in grey, the customer on the right in solid orange */
    [data-testid="stChatMessage"] {{width: fit-content; max-width: 78%; background: #F4F1EE;
                                   border-radius: 6px 18px 18px 18px; padding: 10px 16px; gap: 10px;}}
    [class*="st-key-me_"] [data-testid="stChatMessage"] {{margin-left: auto; flex-direction: row-reverse;
                                                         background: #F26B1D; border-radius: 18px 6px 18px 18px;}}
    [class*="st-key-me_"] [data-testid="stChatMessage"] p {{color: #FFFFFF;}}
    [data-testid="stChatMessage"] p {{font-size: 1rem; line-height: 1.55; color: #2A2A33;}}

    /* Quick-reply chips */
    .st-key-chips button {{background: #FFF6EF; border: 1px solid #F5CFB4; color: #B9500F;
                          font-weight: 600; min-height: 36px;}}
    .st-key-chips button:hover {{background: #F26B1D; border-color: #F26B1D; color: #FFFFFF;}}

    /* Tabs */
    button[data-baseweb="tab"] p {{font-size: 1.05rem; font-weight: 700;}}

    /* Help centre list: clean rows with thin dividers */
    [data-testid="stExpander"] details {{border: none; border-bottom: 1px solid #F1EAE4; border-radius: 0;
                                        background: transparent;}}
    [data-testid="stExpander"] summary {{padding: 11px 2px;}}
    [data-testid="stExpander"] summary p {{font-size: 0.98rem; font-weight: 600;}}
    [data-testid="stExpander"] summary:hover p {{color: #F26B1D;}}
    [data-testid="stExpanderDetails"] {{padding: 0 2px 12px 2px;}}
    [data-testid="stExpanderDetails"] p {{font-size: 0.96rem; color: #45454F; line-height: 1.6;}}
    .st-key-faqlist {{height: calc(100vh - 290px) !important; min-height: 380px;}}

    /* Ticket counters as tiles */
    /* Line icons inside our own HTML (uses the icon font Streamlit already loads) */
    .tg-ico {{font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal;
              font-size: 20px; line-height: 1; vertical-align: -4px; margin-right: 8px; color: #F26B1D;
              font-feature-settings: "liga"; -webkit-font-feature-settings: "liga"; display: inline-block;}}

    /* Help centre: one soft card per topic */
    [class*="st-key-topic_"] {{background: #FFFFFF; border: 1px solid #F1EAE4; border-radius: 16px;
                              padding: 6px 16px 4px 16px; margin-bottom: 4px;}}
    .tg-topic {{display: flex; align-items: center; justify-content: space-between; padding: 10px 0 4px 0;}}
    .tg-topic-name {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.02rem; font-weight: 700;
                    color: #1E1E28;}}
    .tg-count {{font-size: 0.78rem; font-weight: 600; color: #9A6A4A; background: #FFF3EA;
               border-radius: 999px; padding: 3px 10px;}}
    [class*="st-key-topic_"] [data-testid="stExpander"]:last-of-type details {{border-bottom: none;}}
    .tg-answer {{background: #FFF8F3; border-left: 3px solid #F26B1D; border-radius: 8px;
                padding: 10px 14px; font-size: 0.95rem; color: #3A3A44; line-height: 1.6;}}

    /* My tickets: summary tiles with a coloured top line */
    .tg-tiles {{display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 6px 0 4px 0;}}
    .tg-tile {{background: #FFFFFF; border: 1px solid #F1EAE4; border-radius: 14px; padding: 12px 14px;
              border-top: 3px solid var(--accent);}}
    .tg-tile b {{display: block; font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.7rem;
                font-weight: 800; color: #1E1E28; line-height: 1.1;}}
    .tg-tile span {{font-size: 0.85rem; font-weight: 600; color: #6B6B76;}}

    /* My tickets: one card per ticket */
    [class*="st-key-ticket_"] {{background: #FFFFFF; border: 1px solid #F1EAE4; border-radius: 16px;
                               padding: 14px 16px 6px 16px; box-shadow: 0 2px 10px rgba(40, 20, 0, 0.03);}}
    .tg-t-top {{display: flex; align-items: center; justify-content: space-between;}}
    .tg-t-id {{font-family: ui-monospace, Consolas, monospace; font-size: 0.88rem; font-weight: 700;
              color: #6B6B76;}}
    .tg-pill {{font-size: 0.76rem; font-weight: 700; border-radius: 999px; padding: 3px 10px;}}
    .tg-open {{background: #FFF0E5; color: #C2540F;}}
    .tg-closed {{background: #E8F6EE; color: #1E8A4C;}}
    .tg-high {{background: #FDECEC; color: #C53030;}}
    .tg-normal {{background: #F2F0EE; color: #6B6B76;}}
    .tg-t-title {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.05rem; font-weight: 700;
                 color: #1E1E28; margin: 8px 0 4px 0;}}
    .tg-t-msg {{font-size: 0.93rem; color: #55555F; line-height: 1.5;}}
    .tg-t-foot {{display: flex; align-items: center; justify-content: space-between; margin-top: 10px;
                padding-top: 8px; border-top: 1px dashed #EFE7E0; font-size: 0.82rem; color: #8A8A94;}}
    .tg-empty {{text-align: center; padding: 40px 10px; color: #6B6B76;}}
    .tg-empty b {{display: block; font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.1rem;
                 color: #1E1E28; margin-bottom: 4px;}}
    .st-key-ticketlist {{height: calc(100vh - 430px) !important; min-height: 300px;}}

    /* Sign-in page */
    .st-key-signin_page {{min-height: calc(100vh - 130px); justify-content: center;}}  /* centred on screen */
    .tg-hero-title {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 3.1rem; font-weight: 800;
                     line-height: 1.12; letter-spacing: -0.03em; color: #1E1E28 !important; margin: 0 0 18px 0;}}
    .tg-hero-title span {{color: #F26B1D !important;}}
    .tg-hero p {{font-size: 1.15rem; color: #55555F; line-height: 1.65; margin: 0 0 28px 0; max-width: 560px;}}
    .tg-facts {{display: flex; gap: 14px; flex-wrap: wrap;}}
    .tg-fact {{background: #FFFFFF; border: 1px solid #EFE7E0; border-radius: 14px; padding: 14px 18px;
              min-width: 160px; box-shadow: 0 4px 16px rgba(40, 20, 0, 0.04);}}
    .tg-fact b {{display: block; font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.25rem; color: #F26B1D;}}
    .tg-fact span {{font-size: 0.9rem; color: #6B6B76;}}

    /* Sign-in card: narrow, centred, with a soft deep shadow */
    .st-key-signin_card {{max-width: 440px; width: 100%; margin: 0 auto; background: #FFFFFF;
                         border: 1px solid #EFE7E0; border-radius: 22px; padding: 30px 32px 22px 32px;
                         box-shadow: 0 24px 60px rgba(40, 20, 0, 0.10); gap: 0.8rem;}}
    .tg-step {{display: inline-block; margin-left: 10px; font-size: 0.75rem; font-weight: 700;
              color: #B9500F; background: #FFF1E6; border-radius: 999px; padding: 4px 10px; vertical-align: 12px;}}
    .tg-card-title {{font-family: "Plus Jakarta Sans", sans-serif; font-size: 1.6rem; font-weight: 800;
                    color: #1E1E28; letter-spacing: -0.02em; margin: 18px 0 4px 0;}}
    .tg-card-sub {{font-size: 0.95rem; color: #6B6B76; line-height: 1.5;}}
    .tg-card-sub b {{color: #1E1E28;}}
    .st-key-signin_card [data-testid="stForm"] {{border: none; padding: 0;}}
    .st-key-signin_card input {{height: 48px; font-size: 1rem;}}
    .st-key-signin_card [data-testid="stFormSubmitButton"] button {{min-height: 48px; font-size: 1rem;
                                                                   font-weight: 700;}}
    .tg-note {{font-size: 0.82rem; color: #8A8A94; border-top: 1px solid #F1EAE4; padding-top: 14px;
              line-height: 1.5;}}
    </style>
    """,
    unsafe_allow_html=True,
)

# The fixed top bar (shown on every page)
st.markdown(
    f"""
    <div class="tg-nav">
      <div class="tg-brand">{LOGO}<span class="tg-word">TiffinGo</span>
        <span class="tg-divider"></span><span class="tg-area">Help Centre</span></div>
      <div class="tg-nav-right">Support hours <b>11 AM – 11 PM</b>, all days</div>
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


def card_header(step, title, subtitle):
    """The top of the sign-in card: logo, step tag, big title and a short line under it."""
    st.markdown(
        f'<div>{LOGO}<span class="tg-step">Step {step} of 2</span></div>'
        f'<div class="tg-card-title">{title}</div><div class="tg-card-sub">{subtitle}</div>',
        unsafe_allow_html=True,
    )


if not s.get("customer"):
    with st.container(key="signin_page"):  # centred on the screen
        hero, _, card = st.columns([1.2, 0.1, 1], vertical_alignment="center")
        with hero:
            st.markdown(
                """
                <div class="tg-hero">
                  <div class="tg-hero-title">Support for every<br><span>TiffinGo</span> order.</div>
                  <p>Track deliveries, manage your tiffin plan, and resolve payment or refund questions
                     with Tiffy, our support assistant. When you need a person, our team takes over.</p>
                  <div class="tg-facts">
                    <div class="tg-fact"><b>Instant</b><span>answers from our help centre</span></div>
                    <div class="tg-fact"><b>24 hours</b><span>for a reply from our team</span></div>
                    <div class="tg-fact"><b>Private</b><span>your tickets, only for you</span></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with card, st.container(key="signin_card"):  # "signin_card" gets the narrow white card style
            if "otp_email" not in s:
                # Step 1: ask for the email and send the code.
                card_header(1, "Sign in to TiffinGo",
                            "Enter your email and we'll send you a one-time code. No password needed.")
                with st.form("email_form", border=False):
                    typed_email = st.text_input("Email address", placeholder="you@example.com")
                    send = st.form_submit_button("Continue", type="primary", width="stretch")
                if send:
                    email = accounts.clean_email(typed_email)
                    problem = send_otp(email) if email else "That doesn't look like an email address."
                    if problem:
                        st.error(problem)
                    else:
                        st.rerun()
            else:
                # Step 2: check the code they type.
                card_header(2, "Check your email",
                            f"Enter the 6-digit code we sent to <b>{html.escape(s['otp_email'])}</b>. "
                            "It may take a minute, and it could be in your spam folder.")
                with st.form("otp_form", border=False):
                    typed_code = st.text_input("6-digit code", max_chars=6, placeholder="••••••")
                    check = st.form_submit_button("Verify and sign in", type="primary", width="stretch")
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

                with st.container(horizontal=True, horizontal_alignment="distribute"):
                    if st.button("Resend code", type="tertiary", icon=":material/refresh:"):
                        problem = send_otp(s["otp_email"])
                        if problem:
                            st.error(problem)
                        else:
                            st.toast("New code sent.")
                    if st.button("Change email", type="tertiary", icon=":material/edit:"):
                        s.pop("otp_email", None)
                        st.rerun()

            st.markdown(
                '<div class="tg-note"><span class="tg-ico" style="font-size:16px;color:#8A8A94;'
                'margin-right:6px;vertical-align:-3px">lock</span>We only use your email to send your code '
                "and keep your tickets private.</div>",
                unsafe_allow_html=True,
            )
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
    bot_says(f"Done. I've raised ticket **{ticket_id}**. A person from our team will reply within 24 hours.")


def close_chat():
    s["closed"] = True


def log_out():
    for key in ("customer", "session_id", "messages", "pending"):
        s.pop(key, None)


def bubble(role, key):
    """One chat bubble. The customer's bubbles get a key starting with "me_" so the style puts them on the right."""
    with st.container(key=("me_" if role == "user" else "bot_") + str(key)):
        return st.chat_message(role, avatar=TIFFY_AVATAR if role == "assistant" else CUSTOMER_AVATAR)


# Page heading row: title on the left, who is signed in and Log out on the right
title_col, user_col = st.columns([3, 1], vertical_alignment="center")
title_col.markdown(
    '<div class="tg-h1">How can we help you today?</div>'
    '<div class="tg-lead">Chat with Tiffy, browse the help centre, or check your tickets.</div>',
    unsafe_allow_html=True,
)
with user_col.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center"):
    st.caption(f"Signed in as {customer[0]}•••@{customer.split('@')[1]}")
    st.button("Log out", on_click=log_out, type="tertiary", icon=":material/logout:")

left, right = st.columns([1.8, 1], gap="medium")

# ---- Left: the big chat panel ----
with left, st.container(key="chatcard"):  # "chatcard" gets the white card style
    # Header strip: Tiffy's name and status, End chat on the right
    with st.container(key="chathead"):
        head_text, head_button = st.columns([4, 1], vertical_alignment="center")
        head_text.markdown(
            f"""<div class="tg-chat-head">{LOGO}<div><div class="tg-chat-name">Tiffy · TiffinGo Support</div>
            <div class="tg-chat-status"><span class="tg-dot"></span>Online · usually replies in a few seconds</div>
            </div></div>""",
            unsafe_allow_html=True,
        )
        head_button.button("End chat", on_click=close_chat, disabled=s["closed"], type="tertiary",
                           icon=":material/close:")

    chat_box = st.container(height=520, key="chatbox", border=False, autoscroll=True)
    with chat_box:
        for i, m in enumerate(s["messages"]):
            with bubble(m["role"], i):
                st.markdown(m["text"])
        # After the 40-second check-in, offer the two choices as buttons.
        if not s["closed"] and s["messages"][-1]["text"] == NUDGE:
            with st.container(horizontal=True):
                st.button("Connect me to an agent", on_click=connect_agent, icon=":material/support_agent:")
                st.button("Close chat", on_click=close_chat, icon=":material/check_circle:")

    if s["closed"]:
        # ---- Ratings when the chat has ended ----
        if not s["rated"]:
            st.markdown("#### Rate your experience")
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
            st.success("Thank you for your feedback.")
        st.button("Start a new chat", type="primary", on_click=new_chat, icon=":material/chat:")
    else:
        # ---- Quick-reply chips, then the message box ----
        with st.container(horizontal=True, key="chips", gap="small"):
            st.button("Track my order", on_click=ask, args=("I want to track my order.",),
                      icon=":material/local_shipping:")
            st.button("Cancel or refund", on_click=ask, args=("I want to cancel my order or get a refund.",),
                      icon=":material/currency_rupee:")
            st.button("Delivery hours", on_click=ask,
                      args=("What are your delivery hours?", faq_answer("What are your delivery hours?")),
                      icon=":material/schedule:")
            st.button("Talk to an agent", on_click=connect_agent, icon=":material/support_agent:")

        typed = st.chat_input("Type your message...")
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

# ---- Right: help centre and the customer's own tickets (drawn last, so new tickets show) ----
TOPIC_ICONS = {  # names of Google "material" icons shown next to each topic
    "Orders & delivery": "local_shipping", "Payments, cancellations & refunds": "payments",
    "Tiffin plans": "lunch_dining", "Food & allergens": "restaurant", "Account & partners": "manage_accounts",
    "Other questions": "help", "Policies": "gavel",
}


def topic_header(name, count):
    """The header row of one help-centre topic card: icon, name and how many articles it has."""
    icon = TOPIC_ICONS.get(name, "help")
    st.markdown(
        f'<div class="tg-topic"><span class="tg-topic-name"><span class="tg-ico">{icon}</span>{name}</span>'
        f'<span class="tg-count">{count} articles</span></div>',
        unsafe_allow_html=True,
    )


def answer_box(text):
    """An answer in a tinted box with an orange line on the left."""
    safe = html.escape(text).replace("\n", "<br>")  # keep line breaks
    st.markdown(f'<div class="tg-answer">{safe}</div>', unsafe_allow_html=True)


with right, st.container(key="sidepanel"):  # "sidepanel" gets the white card style
    help_tab, tickets_tab = st.tabs(["Help centre", "My tickets"])

    with help_tab:
        with st.container(height=560, border=False, key="faqlist"):
            entries = help_entries()
            faqs = {t[len("FAQ: "):]: a for t, a in entries if t.startswith("FAQ: ")}
            policies = [(t, a) for t, a in entries if not t.startswith("FAQ: ")]
            listed = {q for qs in TOPICS.values() for q in qs}
            groups = dict(TOPICS)
            others = [q for q in faqs if q not in listed]
            if others:
                groups["Other questions"] = others

            for number, (topic, questions) in enumerate(groups.items()):
                questions = [q for q in questions if q in faqs]
                with st.container(key=f"topic_{number}"):  # one soft card per topic
                    topic_header(topic, len(questions))
                    for q in questions:
                        with st.expander(q):
                            answer_box(faqs[q])
                            st.button("Ask Tiffy about this", key=f"faq_{q}", on_click=ask, type="tertiary",
                                      args=(q, faq_answer(q)), disabled=s["closed"],
                                      icon=":material/arrow_forward:")
            with st.container(key="topic_policies"):
                topic_header("Policies", len(policies))
                for title, text in policies:
                    with st.expander(title):
                        answer_box(text)

    with tickets_tab:
        tickets = customer_tickets(customer)  # only this customer's tickets, never anyone else's
        open_count = sum(1 for t in tickets if t["status"] == "open")

        # Summary tiles
        st.markdown(
            f"""<div class="tg-tiles">
              <div class="tg-tile" style="--accent:#9A9AA5"><b>{len(tickets)}</b><span>Total</span></div>
              <div class="tg-tile" style="--accent:#F26B1D"><b>{open_count}</b><span>Open</span></div>
              <div class="tg-tile" style="--accent:#22A35A"><b>{len(tickets) - open_count}</b><span>Closed</span></div>
            </div>""",
            unsafe_allow_html=True,
        )

        if not tickets:
            st.markdown(
                '<div class="tg-empty"><span class="tg-ico" style="font-size:40px;color:#F26B1D">'
                'confirmation_number</span><b>No tickets yet</b>'
                "If Tiffy hands you over to a person, your ticket will show here.</div>",
                unsafe_allow_html=True,
            )
        else:
            show = st.segmented_control("Show", ["All", "Open", "Closed"], default="All",
                                        key="ticket_filter", label_visibility="collapsed") or "All"
            shown = [t for t in tickets if show == "All" or t["status"] == show.lower()]
            with st.container(height=420, border=False, key="ticketlist", gap="small"):
                if not shown:
                    st.caption(f"No {show.lower()} tickets.")
                for t in shown:
                    is_open = t["status"] == "open"
                    with st.container(key=f"ticket_{t['ticket_id']}"):  # one card per ticket
                        # html.escape keeps the customer's text as plain text, never as page code
                        st.markdown(
                            f"""<div class="tg-t-top"><span class="tg-t-id">{html.escape(t['ticket_id'])}</span>
                              <span class="tg-pill {'tg-open' if is_open else 'tg-closed'}">
                              {'Open' if is_open else 'Closed'}</span></div>
                            <div class="tg-t-title">{html.escape(t['reason'].capitalize())}</div>
                            <div class="tg-t-msg">{html.escape(t['message'])}</div>
                            <div class="tg-t-foot"><span>{html.escape(t['time'])}</span>
                              <span class="tg-pill {'tg-high' if t['priority'] == 'high' else 'tg-normal'}">
                              {'High priority' if t['priority'] == 'high' else 'Normal priority'}</span></div>""",
                            unsafe_allow_html=True,
                        )
                        if is_open:
                            st.button("Mark as resolved", key=f"close_{t['ticket_id']}", type="tertiary",
                                      on_click=close_ticket, args=(t["ticket_id"], customer),
                                      icon=":material/task_alt:")
