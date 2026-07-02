#!/usr/bin/env python3
"""Build the MPC textbook RAG index.

Usage:
    python build_rag_index.py [--output app/data/mpc_rag.json]

Requires:
    pip install sentence-transformers
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.rag.retrieve import build_index

# Default: clone MPC textbook from GitHub into /tmp
MPC_REPO = "https://github.com/kucukdemiral/MPC_LectureNotesProject"

if __name__ == "__main__":
    import argparse
    import subprocess
    import tempfile

    parser = argparse.ArgumentParser(description="Build Exobrain RAG index")
    parser.add_argument("--tex-dir", help="Path to LaTeX chapters directory")
    parser.add_argument("--output", default="app/data/mpc_rag.json", help="Output path")
    parser.add_argument("--clone", action="store_true", default=True, help="Clone MPC repo automatically")
    args = parser.parse_args()

    tex_dir = args.tex_dir
    if not tex_dir and args.clone:
        import tempfile
        tmp = tempfile.mkdtemp(prefix="mpc_")
        print(f"Cloning {MPC_REPO} ...")
        subprocess.run(["git", "clone", "--depth", "1", MPC_REPO, tmp], check=True)
        tex_dir = tmp

    if not tex_dir:
        print("Error: --tex-dir is required (or use --clone)", file=sys.stderr)
        sys.exit(1)

    build_index(tex_dir, args.output)
    print(f"\nDone. Index saved to {args.output}")
