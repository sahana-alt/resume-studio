#!/usr/bin/env python3
"""Export a generated cover letter to a formatted Word document."""

from __future__ import annotations

import argparse
from pathlib import Path

from export_resume import build_cover_letter_docx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("name")
    parser.add_argument("email")
    parser.add_argument("phone")
    args = parser.parse_args()

    build_cover_letter_docx(
        args.markdown.read_text(encoding="utf-8"),
        {"name": args.name, "email": args.email, "phone": args.phone},
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
