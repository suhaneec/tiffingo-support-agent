"""
Help-document search (RAG) for TiffinGo.

build_index() reads data/tiffingo_help.txt, cuts it into chunks (one per FAQ and
one per policy), turns each chunk into numbers (an "embedding") with Gemini, and
saves them in a local Chroma database in the "index" folder.

search_help_docs() is the tool Tiffy calls: it finds the 3 chunks closest to the
customer's question.
"""

from pathlib import Path

import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

# The embedding model is set in ONE place: here.
EMBEDDING_MODEL = "gemini-embedding-001"

# Files and folders (all inside the project folder).
PROJECT_DIR = Path(__file__).resolve().parent.parent
HELP_FILE = PROJECT_DIR / "data" / "tiffingo_help.txt"
INDEX_DIR = PROJECT_DIR / "index"
COLLECTION_NAME = "tiffingo_help"
TOP_K = 3  # how many chunks the search returns

# Heading lines in the file that are not part of any chunk.
SKIP_LINES = {"Frequently asked questions", "Policies"}

# Read the Gemini key from the .env file (it is never written in code).
load_dotenv()


def split_into_chunks(text):
    """Cut the help file into chunks: one per FAQ ("Q:") and one per policy ("Policy:").

    Returns a list of (title, chunk_text). The title is shown as the answer's source.
    """
    chunks = []
    title, lines = None, []

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Q:") or line.startswith("Policy:"):
            # A new FAQ or policy begins: save the one we were collecting.
            if title:
                chunks.append((title, "\n".join(lines).strip()))
            if line.startswith("Q:"):
                title = "FAQ: " + line[2:].strip()
            else:
                title = line[len("Policy:"):].strip()  # e.g. "Cancellation and refund policy"
            lines = [line]
        elif title and line and line not in SKIP_LINES:
            lines.append(line)  # part of the current FAQ or policy

    if title:
        chunks.append((title, "\n".join(lines).strip()))
    return chunks


def build_index():
    """Rebuild the search index from the help file. Returns the number of chunks saved."""
    chunks = split_into_chunks(HELP_FILE.read_text(encoding="utf-8"))
    titles = [t for t, _ in chunks]
    texts = [c for _, c in chunks]

    # Turn every chunk into an embedding (one request for all of them).
    client = genai.Client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    embeddings = [e.values for e in result.embeddings]

    # Save in Chroma, replacing any old index.
    db = chromadb.PersistentClient(path=str(INDEX_DIR))
    try:
        db.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # there was no old index
    collection = db.create_collection(COLLECTION_NAME)
    collection.add(
        ids=[f"chunk-{i}" for i in range(len(texts))],
        documents=texts,
        embeddings=embeddings,
        metadatas=[{"source": t} for t in titles],
    )
    return len(texts)


def ensure_index():
    """Build the index if the index folder is missing (for example on Streamlit Cloud)."""
    if not INDEX_DIR.exists():
        build_index()


def search_help_docs(question: str) -> dict:
    """Search TiffinGo's help docs (20 FAQs and 3 policies) for the parts that best match the question.

    Call this before answering any question about TiffinGo: delivery areas and times,
    fees, orders, cancellations, refunds, payments, tiffin plans, food and allergens.

    Args:
        question: The customer's question, in their own words.

    Returns:
        A dict with "results": a list of the 3 closest chunks, each with its
        "text" and its "source" (the FAQ or policy name to show as the source).
    """
    ensure_index()

    # Turn the question into numbers with the SAME model, but as a question.
    client = genai.Client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=question,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    query_embedding = result.embeddings[0].values

    # Ask Chroma for the closest chunks.
    db = chromadb.PersistentClient(path=str(INDEX_DIR))
    collection = db.get_collection(COLLECTION_NAME)
    found = collection.query(query_embeddings=[query_embedding], n_results=TOP_K)

    results = [
        {"text": text, "source": meta["source"]}
        for text, meta in zip(found["documents"][0], found["metadatas"][0])
    ]
    return {"results": results}
