"""Rebuilds the help-docs search index (the "index" folder).

Mac:      .venv/bin/python build_index.py
Windows:  .venv\Scripts\python build_index.py
Run it again whenever you change data/tiffingo_help.txt.
"""

from support_agent.help_docs import build_index

count = build_index()
print(f"Saved {count} chunks to the index folder.")
