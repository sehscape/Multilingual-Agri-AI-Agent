"""One-time script to build the FAISS scheme index.

Usage (from project root, venv active):
    python scripts/build_scheme_index.py

This loads all .txt and .pdf files from data/schemes/raw/,
chunks them, embeds them, and saves the FAISS index to data/vectorstore/.
Run this once before using the scheme tool; re-run when you add new scheme files.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import SCHEMES_RAW_DIR, VECTORSTORE_PATH
from app.rag.scheme_rag import SchemeRAG
from app.utils.logging import get_logger

logger = get_logger("build_scheme_index")


def main():
    print(f"Raw schemes dir : {SCHEMES_RAW_DIR}")
    print(f"Vectorstore dir : {VECTORSTORE_PATH}")

    files = list(Path(SCHEMES_RAW_DIR).glob("*.txt")) + list(Path(SCHEMES_RAW_DIR).glob("*.pdf"))
    if not files:
        print("ERROR: No .txt or .pdf files found in raw schemes directory.")
        sys.exit(1)

    print(f"Found {len(files)} file(s): {[f.name for f in files]}")
    print("\nBuilding index (this downloads the embedding model on first run)...")

    t0 = time.time()
    rag = SchemeRAG()
    rag.build()
    rag.save()
    elapsed = time.time() - t0

    print(f"\nDone in {elapsed:.1f}s")
    print(f"Index saved to: {VECTORSTORE_PATH}")
    print("\nRun a quick sanity query:")
    results = rag.query("How do I apply for PM-KISAN?", top_k=2)
    for r in results:
        print(f"  [{r['source']}] score={r['score']:.3f}: {r['text'][:120]}...")


if __name__ == "__main__":
    main()
