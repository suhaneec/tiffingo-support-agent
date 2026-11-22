# TiffinGo Support: Tiffy 🍱

Tiffy is a customer-support chat agent for **TiffinGo**, a made-up app that delivers home-style meals from partner home kitchens, as single orders or monthly tiffin plans. *All data here is made up for practice.*

Built for the AI Residency (Goa, 20 to 22 Nov 2026) with Google ADK, Gemini and Streamlit.

## What Tiffy does

- Greets customers and only talks about TiffinGo orders, delivery, tiffin plans, payments, refunds and food details.
- Answers from TiffinGo's help docs (20 FAQs and 3 policies) using **RAG**: Gemini embeddings plus a local Chroma index. Each answer names its source.
- Raises **tickets** (`TKT-1001`, `TKT-1002`...) in `tickets.csv` when a person should take over. That happens when someone feels unwell after a meal (high priority), asks for a refund above ₹1,000, complains about a rider, is angry, asks something the docs don't answer, or asks for a person.
- **Guardrails**: it never gives medical advice, never shares a rider's or another customer's phone number, never promises refunds outside the policy, and ignores "ignore your rules" requests.
- **Order lookup**: shows an order only if both the order ID and the last 4 phone digits match.
- **Web page** (`app.py`): customers log in with their email and a one-time code (OTP) sent by email, chat with Tiffy, browse the help topics, and see only their own tickets (total, open, closed). Tiffy checks in after 40 seconds of silence, and customers rate the chat when it ends.

## Files

| File | What it is |
|---|---|
| `support_agent/agent.py` | Tiffy's instructions and tools |
| `support_agent/help_docs.py` | Splits the help docs into chunks, builds the index and searches it |
| `support_agent/tickets.py` | Saves tickets to `tickets.csv` |
| `support_agent/orders.py` | Order status lookup from `data/orders.csv` |
| `data/tiffingo_help.txt` | The help docs |
| `data/orders.csv` | 12 made-up orders |
| `build_index.py` | Rebuilds the `index` folder |
| `test_tricky.py` | Sends the 6 tricky test messages and prints the replies |
| `app.py` | The Streamlit chat page |

## Run it on your laptop (Windows)

1. Create a `.env` file from `.env.example` and fill in `GOOGLE_API_KEY`, `GEMINI_MODEL`, `OTP_EMAIL_ADDRESS` and `OTP_EMAIL_APP_PASSWORD` (a Gmail app password).
2. Set up the project:
   ```
   py -3.13 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
3. Build the index: `.venv\Scripts\python build_index.py`
4. Chat in the ADK page: `.venv\Scripts\adk web`, then open http://127.0.0.1:8000
5. Run the tricky tests: `.venv\Scripts\python test_tricky.py`
6. Open the web page: `.venv\Scripts\streamlit run app.py`

On a Mac, use `.venv/bin/...` instead of `.venv\Scripts\...`.

## Put it online (Streamlit Community Cloud)

1. Push this folder to a GitHub repo. `.env`, `index/` and `tickets.csv` stay off GitHub (see `.gitignore`).
2. Go to [share.streamlit.io](https://share.streamlit.io), click **Create app**, and pick the repo, branch `main` and file `app.py`.
3. Under **Advanced settings → Secrets**, paste the following, using your own values:
   ```
   GOOGLE_API_KEY = "your-key"
   GEMINI_MODEL = "gemini-3.5-flash-lite"
   OTP_EMAIL_ADDRESS = "your-gmail-address@gmail.com"
   OTP_EMAIL_APP_PASSWORD = "your-app-password"
   ```
4. Deploy. The first load builds the index, so it can take a minute.

Notes: `tickets.csv` resets when the online app restarts, which is fine for a demo. Free apps go to sleep when nobody uses them, so open the link 10 minutes before you demo it.
