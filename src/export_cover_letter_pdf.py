#!/usr/bin/env python3
"""Export a generated cover letter to PDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_cover_letter_pdf(
    letter_text: str,
    profile: dict[str, str],
    out_path: Path,
) -> None:
    name = str(profile.get("name", "Your Name"))
    email = str(profile.get("email", "")).strip()
    phone = str(profile.get("phone", "")).strip()
    contact = " | ".join(value for value in (email, phone) if value)

    document = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        leftMargin=1.0 * inch,
        rightMargin=1.0 * inch,
        title="Cover Letter",
        author=name,
    )
    name_style = ParagraphStyle(
        "CoverName",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        spaceAfter=3,
    )
    contact_style = ParagraphStyle(
        "CoverContact",
        fontName="Helvetica",
        fontSize=9.5,
        textColor="#4B4B4B",
        leading=12,
        spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "CoverBody",
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        spaceAfter=12,
    )

    story = [Paragraph(xml_escape(name), name_style)]
    if contact:
        story.append(Paragraph(xml_escape(contact), contact_style))

    paragraphs = [
        paragraph.strip()
        for paragraph in letter_text.replace("\r\n", "\n").split("\n\n")
        if paragraph.strip()
    ]
    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        story.append(Paragraph("<br/>".join(xml_escape(line) for line in lines), body_style))
    story.append(Spacer(1, 1))
    document.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("letter", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("name")
    parser.add_argument("email")
    parser.add_argument("phone")
    args = parser.parse_args()

    build_cover_letter_pdf(
        args.letter.read_text(encoding="utf-8"),
        {"name": args.name, "email": args.email, "phone": args.phone},
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
