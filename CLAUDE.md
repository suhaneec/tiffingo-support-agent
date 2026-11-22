# Project rules for Claude Code

The person you are working with is learning to build an AI agent by prompting you. They are probably not a programmer. They never write or edit code by hand: you do that, and you explain it.

## What this project is

- Tiffy, the customer-support agent for TiffinGo (a made-up home-style food delivery app), built with Google ADK (Python) and Gemini.
- The agent is in `support_agent/agent.py`. `root_agent` is the agent ADK runs. Keep the agent in this folder.
- Settings live in `.env`, which the person copied from `.env.example`. The model name is `GEMINI_MODEL` in `.env`. Never write a model name anywhere else.
- The Python packages are installed in the `.venv` folder. Run Python as `.venv/bin/python` on Mac and `.venv/Scripts/python` on Windows. Do not use the system Python.
- The person starts the agent's chat page (`adk web`) in their own terminal. Do not start it yourself unless they ask. It does not pick up changes by itself: after you change the agent, remind them to restart it (Ctrl+C, then the same command again) and click New Session.
- `data/tiffingo_help.txt` holds the help docs (20 FAQs starting with "Q:", 3 policies starting with "Policy:"). `data/orders.csv` holds 12 made-up orders for the order lookup.
- Tools: `support_agent/help_docs.py` (RAG search, index in the `index` folder), `support_agent/tickets.py` (tickets.csv), `support_agent/orders.py` (order lookup). The web page is `app.py` (Streamlit).
- On Windows, Python is `.venv\Scripts\python`.

## How to work

- Keep code simple, short and commented in plain English. One clear file is better than a clever structure.
- Make only the change you were asked for. Do not add extra features, files or tests.
- When you finish, explain what you changed in a few short lines of plain English, without jargon. Say which file you changed.
- Ask before installing any new package. Everything the course needs is already in `requirements.txt`.
- When you need to check your work against Gemini, use as few requests as you can. The free key has a small daily limit.
- Use Git or GitHub only when the person asks.

## Keys and secrets

- Never read, print or edit `.env`, and never put a key in code or in a message.
- If a new setting is needed, add it to `.env.example` with a placeholder, then tell the person the exact line to add to their own `.env`.
- Never upload or commit `.env`, `.streamlit/secrets.toml`, `.venv/`, `index/` or `tickets.csv`. They are listed in `.gitignore`; keep it that way.
- The agent must never show one customer's data to another customer.
