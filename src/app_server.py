#!/usr/bin/env python3
"""Local web interface for the resume automation workflow."""

from __future__ import annotations

import base64
import hmac
import json
import mimetypes
import os
import re
import sys
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
GENERATED_DIR = ROOT / "generated"
VAULT_PATH = ROOT / "vault" / "career_vault.json"
sys.path.insert(0, str(ROOT / "src"))

from resume_tailor import (  # noqa: E402
    fetch_url_text,
    generate_application_package,
    page_looks_unusable,
    safe_slug,
)


def extract_resume_text(filename: str, payload: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if not payload:
        return ""
    if suffix in {".txt", ".md"}:
        return payload.decode("utf-8", errors="replace")
    if suffix == ".docx":
        with zipfile.ZipFile(__import__("io").BytesIO(payload)) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        words = [
            node.text or ""
            for node in root.iter()
            if node.tag.endswith("}t")
        ]
        return " ".join(words)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(__import__("io").BytesIO(payload))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError("The PDF could not be read. Please upload the DOCX version for cleaner extraction.") from exc
    raise ValueError("Supported resume formats are PDF, DOCX, TXT, and MD.")


def read_preview(path: Path) -> str:
    if path.suffix.lower() not in {".md", ".txt", ".json", ".tex"}:
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name == "tailored_resume.md":
        text = text.split("## Truthfulness Notes", 1)[0].rstrip()
    return text[:30_000]


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "ResumeStudio/1.0"

    def authorized(self) -> bool:
        password = os.getenv("APP_PASSWORD", "")
        if not password:
            return True
        username = os.getenv("APP_USERNAME", "sahana")
        expected = "Basic " + base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        received = self.headers.get("Authorization", "")
        if hmac.compare_digest(received, expected):
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Resume Studio"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def log_message(self, format: str, *args: object) -> None:
        print(f"[app] {format % args}")

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.authorized():
            return
        parsed = urlparse(self.path)
        if parsed.path.startswith("/files/"):
            relative = unquote(parsed.path.removeprefix("/files/"))
            target = (GENERATED_DIR / relative).resolve()
            if GENERATED_DIR.resolve() not in target.parents or not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{target.name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        target = APP_DIR / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
        if not target.is_file() or APP_DIR.resolve() not in target.resolve().parents:
            self.send_error(404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if not self.authorized():
            return
        if self.path != "/api/generate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 15_000_000:
                raise ValueError("Upload is too large. Keep the resume under 15 MB.")
            data = json.loads(self.rfile.read(length) or b"{}")
            url = str(data.get("url", "")).strip()
            jd_text = str(data.get("jd_text", "")).strip()
            instructions = str(data.get("instructions", "")).strip()
            cover_instructions = str(data.get("cover_instructions", "")).strip()
            company_name = str(data.get("company_name", "")).strip()
            role_name = str(data.get("role_name", "")).strip()
            filename = str(data.get("resume_name", "")).strip()
            encoded = str(data.get("resume_data", ""))

            if not jd_text and not url:
                raise ValueError("Paste a job URL or job description.")
            if not jd_text:
                jd_text = fetch_url_text(url)
            if page_looks_unusable(jd_text):
                raise ValueError("The job description is too short or could not be extracted. Paste the JD text below the URL.")

            resume_text = ""
            if encoded:
                resume_text = extract_resume_text(filename, base64.b64decode(encoded))

            company_hint = re.sub(r"^www\\.", "", urlparse(url).netloc).split(".")[0] if url else ""
            slug_base = url or f"{company_hint}-{jd_text[:80]}"
            slug = safe_slug(slug_base)
            result = generate_application_package(
                vault_path=VAULT_PATH,
                out_root=GENERATED_DIR,
                jd_text=jd_text,
                source=url or "Pasted job description",
                slug=slug,
                additional_instructions=instructions,
                attached_resume_text=resume_text,
                attached_resume_name=filename,
                company_name=company_name,
                role_name=role_name,
                cover_letter_instructions=cover_instructions,
            )

            out_dir: Path = result["out_dir"]
            artifact_names = [
                "tailored_resume.docx", "tailored_resume.tex", "tailored_resume.pdf",
                "tailored_resume.md", "cover_letter.txt", "cover_letter.tex",
                "recruiter_dm.md",
                "application_brief.md", "interview_prep.md", "skill_gap_project_plan.md",
            ]
            artifacts = [
                {
                    "name": name,
                    "url": f"/files/{out_dir.name}/{name}",
                    "available": (out_dir / name).exists(),
                }
                for name in artifact_names
            ]
            self.send_json(200, {
                "ok": True,
                "slug": out_dir.name,
                "role_type": result["role_type"],
                "base_source": result["base_source"],
                "bullet_count": len(result["bullets"]),
                "skills": result["jd"]["all_skills"][:12],
                "artifacts": artifacts,
                "previews": {
                    "resume": read_preview(out_dir / "tailored_resume.md"),
                    "cover": read_preview(out_dir / "cover_letter.md"),
                    "coverTex": read_preview(out_dir / "cover_letter.tex"),
                    "dm": read_preview(out_dir / "recruiter_dm.md"),
                    "brief": read_preview(out_dir / "application_brief.md"),
                },
            })
        except SystemExit as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    print(f"Resume Studio running at http://{host}:{port}")
    ThreadingHTTPServer((host, port), AppHandler).serve_forever()


if __name__ == "__main__":
    main()
