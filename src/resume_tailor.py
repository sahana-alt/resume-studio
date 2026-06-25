#!/usr/bin/env python3
"""Tailor application materials from a truthful career vault."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


SKILL_ALIASES = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "node": "Node.js",
    "node.js": "Node.js",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "aws": "AWS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "api": "API design",
    "apis": "API design",
    "testing": "Testing",
    "observability": "Observability",
    "machine learning": "machine learning",
    "ml": "machine learning",
    "artificial intelligence": "AI",
    "generative ai": "Generative AI",
    "large language model": "LLMs",
    "large language models": "LLMs",
    "llm": "LLMs",
    "llms": "LLMs",
    "retrieval-augmented generation": "RAG",
    "retrieval augmented generation": "RAG",
    "rag": "RAG",
    "natural language processing": "NLP",
    "nlp": "NLP",
    "prompt engineering": "Prompt Engineering",
    "model evaluation": "Model Evaluation",
    "data analytics": "Data Analytics",
    "data mining": "Data Mining",
    "statistical analysis": "Statistical Analysis",
    "cloud ai": "Cloud AI Platforms",
    "cloud ai platforms": "Cloud AI Platforms",
    "azure ai": "Azure AI",
    "aws ai": "AWS AI services",
    "aws ai services": "AWS AI services",
    "vertex ai": "GCP Vertex AI",
    "gcp vertex ai": "GCP Vertex AI",
    "intelligent automation": "Intelligent Automation",
    "data pipeline": "data pipelines",
    "data pipelines": "data pipelines",
}

DOMAIN_TERMS = [
    "saas",
    "b2b",
    "b2c",
    "fintech",
    "healthcare",
    "retail",
    "supply chain",
    "merchandising",
    "marketing",
    "developer tools",
    "ai",
    "ml",
    "data",
    "security",
    "ecommerce",
    "marketplace",
    "enterprise",
]

SENIORITY_TERMS = {
    "intern": 1,
    "junior": 1,
    "entry": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
    "principal": 5,
    "lead": 4,
    "manager": 4,
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "our", "that", "the", "their",
    "this", "to", "with", "we", "you", "your",
    "apply", "including", "building", "come", "join", "team", "work", "will",
    "must", "have", "role", "position", "offer", "paid", "variety",
}

BLOCKED_PAGE_HINTS = [
    "enable javascript",
    "access denied",
    "captcha",
    "cloudflare",
    "just a moment",
    "sign in",
]

BUNDLED_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
BUNDLED_NODE_MODULES = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
BUNDLED_PYTHON = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"

RELATED_TECH_GROUPS = {
    "cloud": [
        "AWS", "GCP", "Azure", "AWS AI services", "Azure AI", "GCP Vertex AI",
        "Cloud AI Platforms", "Google Kubernetes Engine", "Kubernetes", "Docker",
    ],
    "frontend": ["React", "Angular", "TypeScript", "JavaScript", "Node.js", "Express.js"],
    "backend": ["Java", "Spring Boot", "FastAPI", "Flask", "Node.js", "REST APIs", "API design", "Microservices"],
    "data_ai": [
        "LLMs", "RAG", "Prompt Engineering", "Model Evaluation", "Statistical Analysis",
        "Data Analytics", "Data Mining", "machine learning", "Generative AI", "NLP",
        "PyTorch", "TensorFlow", "Scikit-Learn",
    ],
    "mobile": ["Swift", "UIKit", "SwiftUI", "CoreData", "URLSession", "iOS"],
}

GENERIC_SKILL_COVERAGE = {
    "ai": {
        "llms", "rag", "prompt engineering", "model evaluation", "machine learning",
        "generative ai", "nlp", "pytorch", "tensorflow", "scikit-learn",
    },
    "cloud ai platforms": {"aws", "azure", "gcp", "kubernetes", "docker"},
    "data mining": {"data analytics", "statistical analysis", "machine learning", "nlp"},
    "intelligent automation": {"data pipelines", "api design", "python", "fastapi", "llms", "rag"},
}

ADJACENT_ONLY_RESUME_TERMS = {
    "aws ai services",
    "azure ai",
    "gcp vertex ai",
    "cloud ai platforms",
    "intelligent automation",
}

ROLE_TYPE_BASE_SOURCE = {
    "ai-data": "resume-ml-2026",
    "ios": "resume-ios-2026",
    "cloud-sre": "resume-cloud-automation-2026",
    "backend-java": "resume-java-2026",
    "full-stack": "resume-fullstack-2026",
    "systems-cpp-linux": "resume-cpp-linux-2026",
}


@dataclass(frozen=True)
class CandidateBullet:
    source_type: str
    parent_name: str
    title: str
    dates: str
    text: str
    skills: list[str]
    domains: list[str]
    metrics: list[str]
    seniority_signals: list[str]
    source_id: str
    score: float
    reasons: list[str]


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9.+#-]*", text)
        if token.lower() not in STOPWORDS and len(token) > 2
    ]


def normalized_phrases(values: list[str]) -> set[str]:
    phrases: set[str] = set()
    for value in values:
        phrase = value.strip().lower()
        if not phrase:
            continue
        phrases.add(phrase)
        if "llm" in phrase or "large language model" in phrase:
            phrases.add("llms")
        if "rag" in phrase or "retrieval" in phrase:
            phrases.add("rag")
        if "evaluation" in phrase or "judge" in phrase:
            phrases.add("model evaluation")
        if "statistic" in phrase:
            phrases.add("statistical analysis")
        if "analytics" in phrase:
            phrases.add("data analytics")
        if "mining" in phrase:
            phrases.add("data mining")
        if "prompt" in phrase:
            phrases.add("prompt engineering")
        if "gpt" in phrase or "openai" in phrase:
            phrases.add("generative ai")
            phrases.add("llms")
    return phrases


def unique_ci(values: set[str] | list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        key = value.lower()
        if key not in seen:
            seen[key] = value
    return sorted(seen.values(), key=str.lower)


def flatten_skills(vault: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    for name, group in vault.get("skills", {}).items():
        if name == "product_domains":
            continue
        if isinstance(group, list):
            skills.extend(str(item) for item in group)
    return sorted(set(skills), key=str.lower)


def related_terms(term: str) -> set[str]:
    term_lower = term.lower()
    related: set[str] = set()
    for group in RELATED_TECH_GROUPS.values():
        lowered = {item.lower() for item in group}
        if term_lower in lowered:
            related.update(lowered)
    return related


def adjacent_skill_hits(jd_skills: list[str], bullet_skills: list[str]) -> set[str]:
    bullet_norm = normalized_phrases(bullet_skills)
    hits = set()
    for skill in jd_skills:
        related = related_terms(skill)
        if related and bullet_norm & related:
            hits.add(skill.lower())
    return hits


def is_generically_covered(skill: str, owned_skills: set[str]) -> bool:
    """Treat broad ATS terms as covered only when concrete evidence exists."""
    normalized = normalized_phrases([skill])
    if normalized & owned_skills:
        return True
    for term in normalized:
        coverage = GENERIC_SKILL_COVERAGE.get(term, set())
        if coverage and coverage & owned_skills:
            return True
    return False


def extract_jd(jd_text: str, known_skills: list[str]) -> dict[str, Any]:
    lower = jd_text.lower()
    known_lookup = {skill.lower(): skill for skill in known_skills}
    found_skills = set()

    for raw, canonical in SKILL_ALIASES.items():
        if re.search(rf"\b{re.escape(raw)}\b", lower):
            found_skills.add(canonical)

    for raw, canonical in known_lookup.items():
        if re.search(rf"\b{re.escape(raw)}\b", lower):
            found_skills.add(canonical)

    domains = sorted(
        term for term in DOMAIN_TERMS if re.search(rf"\b{re.escape(term)}\b", lower)
    )
    seniority_hits = {
        term: level
        for term, level in SENIORITY_TERMS.items()
        if re.search(rf"\b{re.escape(term)}\b", lower)
    }
    seniority = max(seniority_hits, key=seniority_hits.get) if seniority_hits else "unspecified"
    heading_text = " ".join(jd_text.splitlines()[:8]).lower()
    for term in ("intern", "junior", "entry", "mid", "senior", "staff", "principal", "lead"):
        if re.search(rf"\b{term}\b", heading_text):
            seniority = term
            break

    responsibility_patterns = [
        r"(?:responsibilities include|you will|responsible for)\s+(.+?)(?:\.|\n\n)",
        r"(?:build|design|improve|lead|own|mentor|collaborate|translate)\s+[^.]+",
    ]
    responsibilities: list[str] = []
    for pattern in responsibility_patterns:
        responsibilities.extend(match.strip() for match in re.findall(pattern, jd_text, re.I | re.S))

    keywords = [
        word
        for word, count in Counter(tokenize(jd_text)).most_common(40)
        if count > 1 or word in {skill.lower() for skill in found_skills}
    ]

    required = infer_requirement_bucket(
        jd_text,
        found_skills,
        ["required", "requires", "must", "need"],
        stop_markers=["preferred", "nice to have", "bonus"],
    )
    preferred = infer_requirement_bucket(
        jd_text,
        found_skills,
        ["preferred", "nice to have", "bonus"],
    )

    return {
        "required_skills": unique_ci(required) or unique_ci(found_skills),
        "preferred_skills": unique_ci(preferred),
        "all_skills": unique_ci(found_skills),
        "responsibilities": responsibilities[:12],
        "keywords": keywords,
        "seniority_level": seniority,
        "domain_signals": domains,
    }


def infer_requirement_bucket(
    jd_text: str,
    skills: set[str],
    markers: list[str],
    stop_markers: list[str] | None = None,
) -> set[str]:
    bucket = set()
    sentences = re.split(r"(?<=[.!?])\s+", jd_text)
    for sentence in sentences:
        lower = sentence.lower()
        if any(marker in lower for marker in markers):
            if stop_markers:
                stop_positions = [
                    lower.find(marker)
                    for marker in stop_markers
                    if lower.find(marker) > -1
                ]
                if stop_positions:
                    lower = lower[:min(stop_positions)]
            for skill in skills:
                if skill.lower() in lower:
                    bucket.add(skill)
    return bucket


def iter_bullets(vault: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in vault.get("experience", []):
        dates = format_dates(role.get("start", ""), role.get("end", ""))
        for bullet in role.get("bullets", []):
            rows.append({
                "source_type": "experience",
                "parent_name": role.get("company", ""),
                "title": role.get("title", ""),
                "dates": dates,
                "text": bullet.get("text", ""),
                "skills": bullet.get("skills", []),
                "domains": bullet.get("domains", []) or role.get("domain_context", []),
                "metrics": bullet.get("metrics", []),
                "seniority_signals": bullet.get("seniority_signals", []),
                "source_id": bullet.get("source_id", ""),
            })
    for project in vault.get("projects", []):
        dates = format_dates(project.get("start", ""), project.get("end", ""))
        for bullet in project.get("bullets", []):
            rows.append({
                "source_type": "project",
                "parent_name": project.get("name", ""),
                "title": "Project",
                "dates": dates,
                "text": bullet.get("text", ""),
                "skills": bullet.get("skills", []),
                "domains": bullet.get("domains", []) or project.get("domain_context", []),
                "metrics": bullet.get("metrics", []),
                "seniority_signals": bullet.get("seniority_signals", []),
                "source_id": bullet.get("source_id", ""),
            })
    return rows


def score_bullet(row: dict[str, Any], jd: dict[str, Any]) -> CandidateBullet | None:
    if not row["text"] or not row["source_id"]:
        return None

    jd_required = normalized_phrases(jd["required_skills"])
    jd_preferred = normalized_phrases(jd["preferred_skills"])
    jd_all = normalized_phrases(jd["all_skills"])
    jd_domains = normalized_phrases(jd["domain_signals"])
    jd_keywords = set(jd["keywords"])

    bullet_skills = normalized_phrases(row["skills"])
    bullet_domains = normalized_phrases(row["domains"])
    bullet_words = set(tokenize(row["text"]))

    required_hits = bullet_skills & jd_required
    preferred_hits = bullet_skills & jd_preferred
    all_skill_hits = bullet_skills & jd_all
    adjacent_hits = adjacent_skill_hits(jd["all_skills"], row["skills"]) - all_skill_hits
    domain_hits = bullet_domains & jd_domains
    keyword_hits = bullet_words & jd_keywords

    if not (all_skill_hits or adjacent_hits or domain_hits) and len(keyword_hits) < 2:
        return None

    score = 0.0
    score += 6 * len(required_hits)
    score += 3 * len(preferred_hits)
    score += 4 * len(all_skill_hits - required_hits - preferred_hits)
    score += 1.5 * len(adjacent_hits)
    score += 3 * len(domain_hits)
    score += min(6, len(keyword_hits))
    score += 2 if row["metrics"] and (all_skill_hits or adjacent_hits or domain_hits) else 0
    score += 1 if row["seniority_signals"] else 0

    if score <= 0:
        return None

    reasons = []
    if required_hits:
        reasons.append("required skills: " + ", ".join(sorted(required_hits)))
    if preferred_hits:
        reasons.append("preferred skills: " + ", ".join(sorted(preferred_hits)))
    other_skill_hits = all_skill_hits - required_hits - preferred_hits
    if other_skill_hits:
        reasons.append("skill match: " + ", ".join(sorted(other_skill_hits)))
    if adjacent_hits:
        reasons.append("adjacent tech match: " + ", ".join(sorted(adjacent_hits)))
    if domain_hits:
        reasons.append("domain match: " + ", ".join(sorted(domain_hits)))
    if keyword_hits:
        reasons.append("keyword overlap: " + ", ".join(sorted(keyword_hits)[:8]))
    if row["metrics"]:
        reasons.append("has metric")

    return CandidateBullet(
        source_type=row["source_type"],
        parent_name=row["parent_name"],
        title=row["title"],
        dates=row["dates"],
        text=row["text"],
        skills=row["skills"],
        domains=row["domains"],
        metrics=row["metrics"],
        seniority_signals=row["seniority_signals"],
        source_id=row["source_id"],
        score=score,
        reasons=reasons,
    )


def candidate_from_row(row: dict[str, Any], score: float, reasons: list[str]) -> CandidateBullet:
    return CandidateBullet(
        source_type=row["source_type"],
        parent_name=row["parent_name"],
        title=row["title"],
        dates=row["dates"],
        text=row["text"],
        skills=row["skills"],
        domains=row["domains"],
        metrics=row["metrics"],
        seniority_signals=row["seniority_signals"],
        source_id=row["source_id"],
        score=score,
        reasons=reasons,
    )


def bullet_key(item: CandidateBullet) -> tuple[str, str, str, str]:
    return (item.source_type, item.parent_name, item.title, item.text)


def specificity_score(item: CandidateBullet) -> int:
    score = 0
    score += 2 if item.metrics else 0
    score += min(3, len(item.skills))
    score += 1 if re.search(r"\b[A-Z][A-Za-z0-9.+#-]{2,}\b", item.text) else 0
    score += 1 if re.search(r"\b(dataset|pipeline|api|model|service|cluster|cache|vector|postgres|mongodb|docker|kubernetes|firebase|swift|spring|fastapi)\b", item.text, re.I) else 0
    score += 1 if re.search(r"\b\d+(\.\d+)?%|\b\d+(\.\d+)?\b", item.text) else 0
    return score


def select_bullets(
    vault: dict[str, Any],
    jd: dict[str, Any],
    limit: int,
    base_source: str | None = None,
    extra_limit: int = 4,
) -> list[CandidateBullet]:
    rows = iter_bullets(vault)
    scored = [
        candidate
        for row in rows
        if (candidate := score_bullet(row, jd)) is not None
    ]
    scored_by_key = {bullet_key(item): item for item in scored}

    if not base_source:
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    selected: list[CandidateBullet] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        if row["source_id"] != base_source:
            continue
        fallback = candidate_from_row(
            row,
            0.0,
            [f"kept from base uploaded resume `{base_source}`"],
        )
        item = scored_by_key.get(bullet_key(fallback), fallback)
        selected.append(item)
        seen.add(bullet_key(item))

    additions = [
        item for item in sorted(scored, key=lambda candidate: candidate.score, reverse=True)
        if (
            bullet_key(item) not in seen
            and item.source_id != base_source
            and specificity_score(item) >= 4
        )
    ][:extra_limit]
    selected.extend(additions)

    if selected:
        return selected
    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def safe_slug(value: str) -> str:
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        value = f"{parsed.netloc}-{parsed.path.strip('/') or 'job'}"
    else:
        value = Path(value).stem
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()[:80] or "job"


def strip_html(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>", "\n", page)
    page = re.sub(r"(?i)</(p|div|li|h[1-6]|section|article|tr)>", "\n", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t]+", " ", page)
    page = re.sub(r"\n\s*\n\s*\n+", "\n\n", page)
    return page.strip()


def fetch_url_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 ResumeTailor/1.0"
            )
        },
    )
    try:
        content_type, raw = open_url(request)
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not fetch URL: {exc}. If the site blocks scraping, paste the JD text into a file and run the CLI on that file."
        ) from exc

    if "pdf" in content_type.lower():
        raise SystemExit("This URL appears to be a PDF. Download it first, extract the JD text, then run the CLI on the text file.")

    text = strip_html(raw.decode("utf-8", errors="replace"))
    if page_looks_unusable(text):
        browser_text = fetch_url_text_with_browser(url)
        if not page_looks_unusable(browser_text):
            return browser_text
        raise SystemExit(
            "Fetched page did not look like a usable job description. The site may require JavaScript, login, or CAPTCHA. "
            "The browser fallback also could not extract a usable JD. Paste the JD text into a file for this run."
        )
    return text


def page_looks_unusable(text: str) -> bool:
    lower = text.lower()
    job_signals = [
        "responsibilities",
        "qualifications",
        "requirements",
        "required",
        "preferred",
        "engineer",
        "developer",
        "job",
        "role",
    ]
    has_job_signal = any(signal in lower for signal in job_signals)
    return len(text) < 350 or not has_job_signal or any(hint in lower[:3000] for hint in BLOCKED_PAGE_HINTS)


def fetch_url_text_with_browser(url: str) -> str:
    helper = Path(__file__).with_name("browser_fetch_jd.cjs")
    node = BUNDLED_NODE if BUNDLED_NODE.exists() else "node"
    env = os.environ.copy()
    if BUNDLED_NODE_MODULES.exists():
        env["NODE_PATH"] = str(BUNDLED_NODE_MODULES)

    try:
        result = subprocess.run(
            [str(node), str(helper), url],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    if result.returncode != 0:
        return ""

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    return str(payload.get("text", ""))


def open_url(request: urllib.request.Request) -> tuple[str, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.headers.get("content-type", ""), response.read(2_000_000)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=20, context=context) as response:
                return response.headers.get("content-type", ""), response.read(2_000_000)
        raise


def read_jd_source(args: argparse.Namespace) -> tuple[str, str, str]:
    if args.url:
        return fetch_url_text(args.url), args.url, safe_slug(args.url)
    if not args.jd:
        raise SystemExit("Provide either a JD file path or --url.")
    return args.jd.read_text(encoding="utf-8"), str(args.jd), safe_slug(str(args.jd))


def metric_phrase(item: CandidateBullet) -> str:
    return f" ({'; '.join(item.metrics[:2])})" if item.metrics else ""


def display_role_title(company: str, title: str, role_type: str | None) -> str:
    """Use recruiter-friendly target titles without changing company names/dates."""
    if company == "Virginia Tech - CodeKids" and role_type == "ai-data":
        return "AI Engineer"
    if company == "Virginia Tech - CodeKids" and role_type in {
        "backend-java",
        "full-stack",
        "cloud-sre",
        "systems-cpp-linux",
    }:
        return "Software Engineer"
    return title


def render_resume(
    vault: dict[str, Any],
    bullets: list[CandidateBullet],
    jd: dict[str, Any],
    role_type: str | None = None,
) -> str:
    profile = vault.get("profile", {})
    matched_skills = pick_relevant_skills(vault, jd)
    experience_bullets = [item for item in bullets if item.source_type == "experience"]
    project_bullets = [item for item in bullets if item.source_type == "project"]

    grouped_experience: dict[tuple[str, str, str], list[CandidateBullet]] = {}
    for bullet in experience_bullets:
        key = (bullet.parent_name, bullet.title, bullet.dates)
        grouped_experience.setdefault(key, []).append(bullet)

    grouped_projects: dict[tuple[str, str], list[CandidateBullet]] = {}
    for bullet in project_bullets:
        key = (bullet.parent_name, bullet.dates)
        grouped_projects.setdefault(key, []).append(bullet)

    lines = [
        f"# {profile.get('name', 'Your Name')}",
        contact_line(profile),
        "",
        "## SUMMARY",
        role_summary(jd, bullets),
        "",
        "## EDUCATION",
    ]
    lines.extend(render_education(vault))

    lines.append("## WORK EXPERIENCE")
    for (parent, title, dates), items in grouped_experience.items():
        lines.extend(["", f"### {parent} - {display_role_title(parent, title, role_type)}\t{dates}"])
        for item in items:
            lines.append(f"- {item.text}")

    skill_rows = render_skill_rows(matched_skills)
    if skill_rows:
        lines.extend(["", "## TECHNICAL SKILLS", *skill_rows])

    if grouped_projects:
        lines.extend(["", "## PROJECTS"])
    for (parent, dates), items in grouped_projects.items():
        lines.extend(["", f"### {parent}\t{dates}"])
        for item in items:
            lines.append(f"- {item.text}")

    publications = vault.get("publications", [])
    if publications:
        lines.extend(["", "## PUBLICATIONS"])
        lines.append("- " + "; ".join(publications))

    awards = vault.get("awards", [])
    if awards:
        lines.extend(["", "## AWARDS AND RECOGNITION"])
        lines.append("- " + "; ".join(awards))

    lines.extend(["", "## Truthfulness Notes"])
    for item in bullets:
        lines.append(f"- `{item.source_id}` -> {item.parent_name}: {'; '.join(item.reasons)}")
    return "\n".join(lines).strip() + "\n"


def contact_line(profile: dict[str, Any]) -> str:
    links = profile.get("links", [])
    link_labels = []
    for link in links:
        if "linkedin" in link.lower():
            link_labels.append("LinkedIn")
        elif "github" in link.lower():
            link_labels.append("Github")
    parts = [profile.get("email", ""), profile.get("phone", ""), *link_labels]
    return " | ".join(part for part in parts if part)


def render_education(vault: dict[str, Any]) -> list[str]:
    schools = {item.get("school", ""): item for item in vault.get("education", [])}
    vt = schools.get("Virginia Tech", {})
    bms = schools.get("BMS College of Engineering", {})
    return [
        f"Virginia Tech - CGPA: 4/4\t{format_dates(vt.get('start', ''), vt.get('end', ''))}",
        "Master of Science in Computer Science and Applications (Thesis Track)",
        "",
        f"BMS College of Engineering - CGPA: 3.99/4\t{format_dates(bms.get('start', ''), bms.get('end', ''))}",
        "Bachelor of Computer Science - Department Silver Medalist (2nd place)",
        "",
    ]


def format_dates(start: str, end: str) -> str:
    return f"{format_month_year(start)} - {format_month_year(end)}".strip(" -")


def format_month_year(value: str) -> str:
    if not value or value.lower() == "present":
        return value
    months = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
    }
    match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if not match:
        return value
    year, month = match.groups()
    return f"{months.get(month, month)} {year}"


def role_summary(jd: dict[str, Any], bullets: list[CandidateBullet]) -> str:
    skills = {skill.lower() for skill in jd.get("all_skills", [])}
    if {"llms", "rag", "model evaluation"} & skills or "machine learning" in skills:
        return (
            "AI/ML engineer with experience building LLM applications, RAG pipelines, "
            "model evaluation frameworks, data analytics workflows, and ML forecasting systems. "
            "Published ACM ICER 2025 work on answer-aware LLM hints and IEEE INOCON 2020 work on demand forecasting."
        )
    return "Software engineer with experience building production software across backend, cloud, mobile, and AI-powered systems."


def pick_relevant_skills(vault: dict[str, Any], jd: dict[str, Any]) -> list[str]:
    vault_skills = {skill.lower(): skill for skill in flatten_skills(vault)}
    priority = [
        "LLMs", "RAG", "Prompt Engineering", "Model Evaluation", "Statistical Analysis",
        "Data Analytics", "Data Mining", "machine learning", "Generative AI", "NLP",
        "GPT-4-Turbo", "OpenAI API", "PyTorch", "TensorFlow", "Scikit-Learn",
        "AWS", "Azure", "GCP", "Kubernetes", "Docker", "API design", "Python", "SQL",
    ]
    selected = []
    for skill in jd.get("all_skills", []):
        skill_key = skill.lower()
        if skill_key in vault_skills:
            selected.append(vault_skills[skill_key])
            continue
        if (
            is_generically_covered(skill, set(vault_skills))
            and skill_key not in ADJACENT_ONLY_RESUME_TERMS
        ):
            selected.append(skill)
            continue
        for owned in flatten_skills(vault):
            if owned.lower() in related_terms(skill):
                selected.append(owned)
    jd_or_related = {skill.lower() for skill in selected}
    jd_related_terms = set().union(*(related_terms(skill) for skill in jd.get("all_skills", []))) if jd.get("all_skills") else set()
    for skill in priority:
        if skill.lower() in vault_skills and (
            skill.lower() in jd_or_related or skill.lower() in jd_related_terms
        ):
            selected.append(vault_skills[skill.lower()])
        elif (
            skill.lower() not in ADJACENT_ONLY_RESUME_TERMS
            and is_generically_covered(skill, set(vault_skills))
            and skill.lower() in {item.lower() for item in jd.get("all_skills", [])}
        ):
            selected.append(skill)
    selected = unique_ci(selected)
    return selected[:18]


def render_skill_rows(skills: list[str]) -> list[str]:
    groups = {
        "Languages": ["Python", "SQL", "Java", "JavaScript", "TypeScript", "Swift"],
        "AI/ML": [
            "LLMs", "RAG", "Prompt Engineering", "Model Evaluation", "Statistical Analysis",
            "Data Analytics", "Data Mining", "machine learning", "Generative AI", "NLP",
            "GPT-4-Turbo", "OpenAI API", "PyTorch", "TensorFlow", "Scikit-Learn",
        ],
        "Technologies/Frameworks": [
            "Cloud AI Platforms", "AWS AI services", "Azure AI", "GCP Vertex AI",
            "AWS", "Azure", "GCP", "Google Kubernetes Engine", "Kubernetes", "Docker",
            "API design", "FastAPI", "PostgreSQL",
        ],
    }
    remaining = list(skills)
    rows = []
    for category, priority in groups.items():
        values = [skill for skill in priority if skill in remaining]
        remaining = [skill for skill in remaining if skill not in values]
        if values:
            rows.append(f"{category}: {', '.join(values)}")
    if remaining:
        rows.append(f"Additional: {', '.join(remaining[:8])}")
    return rows


def render_cover(
    profile: dict[str, Any],
    jd: dict[str, Any],
    bullets: list[CandidateBullet],
    additional_instructions: str = "",
    attached_resume_text: str = "",
    company_name: str = "",
    role_name: str = "",
) -> str:
    resume_words = set(tokenize(attached_resume_text))
    instruction_words = set(tokenize(additional_instructions))

    def cover_relevance(item: CandidateBullet) -> tuple[int, int, float]:
        bullet_words = set(tokenize(item.text))
        resume_overlap = len(bullet_words & resume_words) if resume_words else 1
        instruction_overlap = len(bullet_words & instruction_words)
        return (1 if resume_overlap >= 4 else 0, instruction_overlap, item.score)

    instructions_lower = additional_instructions.lower()
    proof_count = 1 if any(term in instructions_lower for term in ("concise", "short", "brief")) else 2
    top = sorted(bullets, key=cover_relevance, reverse=True)[:max(2, proof_count)]
    skill_phrase = ", ".join(jd["required_skills"][:5]) or "the role's core requirements"
    company = company_name.strip() or "[Company Name]"
    role = role_name.strip() or "[Role Title]"

    first_paragraph = (
        f"I am applying for the {role} position at {company}. "
        "I am looking for a role where I can contribute to real products, keep learning, "
        "and work closely with people who care about thoughtful engineering."
    )

    proof_sentences = []
    if top:
        first = top[0].text.rstrip(".")
        proof_sentences.append(f"In my recent work, I {first[0].lower() + first[1:]}.")
        if proof_count > 1 and len(top) > 1:
            second = top[1].text.rstrip(".")
            proof_sentences.append(f"I also {second[0].lower() + second[1:]}.")

    second_paragraph = (
        f"I believe the role is a strong fit because my background includes {skill_phrase}. "
        + " ".join(proof_sentences)
        + " I am comfortable using AI coding tools, including Codex, for prototyping, debugging, "
          "test generation, and documentation while reviewing the output carefully and keeping "
          "engineering judgment with the developer."
    )

    lines = [
        "Dear Hiring Team,",
        "",
        first_paragraph,
        "",
        second_paragraph,
    ]
    motivation_match = re.search(
        r"mention\s+why\s+(.+?)\s+interests\s+me",
        additional_instructions,
        re.I,
    )
    motivation = (
        motivation_match.group(1).strip(" .")
        if motivation_match
        else f"the problems described in this {role} position"
    )
    third_paragraph = (
        f"What excites me most is {motivation} and the chance to contribute at meaningful production scale. "
        "As a person, I am curious, practical, and collaborative. I enjoy taking ownership, asking clear "
        "questions, and turning an uncertain problem into something useful. I can start immediately and "
        "am willing to relocate for the role."
    )
    lines.extend([
        "",
        third_paragraph,
        "",
        f"Sincerely,\n{profile.get('name', 'Your Name')}",
    ])
    return "\n".join(lines).replace("—", ",").replace("–", "-") + "\n"


def render_cover_latex(markdown: str, profile: dict[str, Any]) -> str:
    def escape(value: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }
        return "".join(replacements.get(char, char) for char in value)

    content = [
        line.strip()
        for line in markdown.splitlines()
        if line.strip() and not line.startswith("# ")
    ]
    greeting = content[0] if content else "Dear Hiring Team,"
    signoff_index = next(
        (index for index, line in enumerate(content) if line == "Sincerely,"),
        len(content),
    )
    paragraphs = content[1:signoff_index]
    name = profile.get("name", "Your Name")
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    body = "\n\n".join(escape(paragraph) for paragraph in paragraphs)

    return "\n".join([
        r"\documentclass[11pt,letterpaper]{letter}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{10pt}",
        rf"\signature{{{escape(name)}}}",
        rf"\address{{{escape(name)} \\ {escape(email)} \\ {escape(phone)}}}",
        r"\begin{document}",
        r"\begin{letter}{Hiring Team \\ [Company Name]}",
        r"\opening{" + escape(greeting) + "}",
        body,
        r"\closing{Sincerely,}",
        r"\end{letter}",
        r"\end{document}",
        "",
    ])


def render_dm(profile: dict[str, Any], jd: dict[str, Any], bullets: list[CandidateBullet]) -> str:
    proof = bullets[0].text + metric_phrase(bullets[0]) if bullets else "my background lines up with the role requirements"
    skills = ", ".join(jd["required_skills"][:3])
    return (
        "# Recruiter DM\n\n"
        "Hi [Name], I saw the opening and it looks closely aligned with my background"
        f"{f' in {skills}' if skills else ''}. "
        f"One relevant example: {proof} I would love to connect if the team is still speaking with candidates.\n\n"
        f"- {profile.get('name', 'Your Name')}\n"
    )


def render_application_brief(jd: dict[str, Any], bullets: list[CandidateBullet], source: str) -> str:
    alignments = ats_alignment_notes(jd, bullets)
    lines = [
        "# Application Brief",
        "",
        f"Source: {source}",
        "",
        "## JD Targets",
        f"- Seniority: {jd['seniority_level']}",
        f"- Required skills: {', '.join(jd['required_skills']) or 'Not detected'}",
        f"- Preferred skills: {', '.join(jd['preferred_skills']) or 'Not detected'}",
        f"- Domain signals: {', '.join(jd['domain_signals']) or 'Not detected'}",
        "",
        "## ATS Technology Alignment",
    ]
    lines.extend(f"- {note}" for note in alignments)
    lines.extend([
        "",
        "## Use These Specific Points",
    ])
    for item in bullets[:10]:
        lines.append(f"- {item.text}{metric_phrase(item)}")
        lines.append(f"  Source: `{item.source_id}`; why: {'; '.join(item.reasons)}")
    lines.extend([
        "",
        "## Review Checklist",
        "- Confirm company name and role title if the URL parser did not extract them cleanly.",
        "- Remove any bullet that feels less relevant than another true bullet in the vault.",
        "- Do not add experience that is not already supported by the vault.",
    ])
    return "\n".join(lines) + "\n"


def ats_alignment_notes(jd: dict[str, Any], bullets: list[CandidateBullet]) -> list[str]:
    bullet_skills = sorted({skill for item in bullets for skill in item.skills}, key=str.lower)
    bullet_norm = normalized_phrases(bullet_skills)
    notes = []
    for skill in jd.get("all_skills", []):
        if is_generically_covered(skill, bullet_norm):
            notes.append(f"`{skill}` has direct support in selected bullets.")
            continue
        owned_related = sorted(
            {candidate for candidate in bullet_skills if candidate.lower() in related_terms(skill)},
            key=str.lower,
        )
        if owned_related:
            notes.append(f"`{skill}` is adjacent to truthful experience with {', '.join(owned_related[:5])}. Use aligned wording, but do not claim direct production experience unless true.")
    return notes or ["No special adjacent-technology substitutions were needed."]


def render_skill_gap_project_plan(jd: dict[str, Any], vault: dict[str, Any]) -> str:
    vault_skills = set(normalized_phrases(flatten_skills(vault)))
    missing = []
    adjacent = []
    for skill in jd.get("all_skills", []):
        if is_generically_covered(skill, vault_skills):
            continue
        owned_related = sorted(
            {
                owned
                for owned in flatten_skills(vault)
                if owned.lower() in related_terms(skill)
            },
            key=str.lower,
        )
        if owned_related:
            adjacent.append((skill, owned_related[:6]))
        else:
            missing.append(skill)

    lines = [
        "# One-Week Skill Gap Project Plan",
        "",
        "Use this only for skills that are missing or weak in the vault. Do not add project bullets to the vault until the project is actually built and evidence exists.",
        "",
    ]
    if adjacent:
        lines.append("## Adjacent Skills To Leverage")
        for skill, owned in adjacent:
            lines.append(f"- JD asks for `{skill}`; closest truthful experience: {', '.join(owned)}.")
        lines.append("")
    if missing:
        lines.append("## Missing Skills")
        lines.extend(f"- `{skill}`" for skill in missing)
        lines.append("")
    if not missing and not adjacent:
        lines.append("No meaningful skill gap detected for this JD.")
        return "\n".join(lines) + "\n"

    focus = ", ".join([skill for skill, _ in adjacent[:3]] + missing[:3]) or "the target skill set"
    lines.extend([
        "## Suggested One-Week Project",
        f"Build a small, deployable project demonstrating {focus} using a role-relevant dataset and a clean README.",
        "",
        "## 7-Day Build Plan",
        "- Day 1: Define the use case, success metric, dataset, and architecture diagram.",
        "- Day 2: Build the core data/API pipeline and commit a minimal working version.",
        "- Day 3: Add the missing or adjacent technology explicitly, with tests or evaluation output.",
        "- Day 4: Add logging, error handling, and a repeatable run script.",
        "- Day 5: Create a short dashboard, notebook, or demo endpoint.",
        "- Day 6: Write the README with screenshots, metrics, tradeoffs, and setup steps.",
        "- Day 7: Polish, deploy if possible, record a short demo, and add only truthful bullets to the vault.",
        "",
        "## Evidence To Capture",
        "- GitHub repository link",
        "- README with architecture and setup",
        "- Screenshots or short demo video",
        "- Quantitative result, latency, accuracy, cost, or evaluation metric",
        "- One or two bullets that truthfully describe what was built",
    ])
    return "\n".join(lines) + "\n"


def render_interview_notes(jd: dict[str, Any], bullets: list[CandidateBullet]) -> str:
    lines = [
        "# Interview Prep Notes",
        "",
        "## JD Signals",
        f"- Seniority: {jd['seniority_level']}",
        f"- Required skills: {', '.join(jd['required_skills']) or 'Not detected'}",
        f"- Preferred skills: {', '.join(jd['preferred_skills']) or 'Not detected'}",
        f"- Domains: {', '.join(jd['domain_signals']) or 'Not detected'}",
        "",
        "## Best Proof Points",
    ]
    for item in bullets[:8]:
        lines.append(f"- {item.text} (`{item.source_id}`)")
    lines.extend(["", "## Likely Questions"])
    for skill in jd["required_skills"][:8]:
        lines.append(f"- Tell me about a time you used {skill} in production.")
    lines.extend([
        "- Which tradeoffs did you make, and what would you improve now?",
        "- How did you measure success?",
        "- How did you collaborate across product, design, or engineering?",
    ])
    return "\n".join(lines) + "\n"


def write_tracker_row(out_dir: Path, source: str, jd: dict[str, Any], bullets: list[CandidateBullet]) -> None:
    tracker = out_dir / "application_tracker.csv"
    exists = tracker.exists()
    with tracker.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date", "job_source", "seniority", "required_skills", "domains",
            "top_sources", "status", "notes"
        ])
        if not exists:
            writer.writeheader()
        writer.writerow({
            "date": date.today().isoformat(),
            "job_source": source,
            "seniority": jd["seniority_level"],
            "required_skills": "; ".join(jd["required_skills"]),
            "domains": "; ".join(jd["domain_signals"]),
            "top_sources": "; ".join(item.source_id for item in bullets[:5]),
            "status": "drafted",
            "notes": "Manual review required before applying.",
        })


def infer_role_type(jd: dict[str, Any], jd_text: str) -> str:
    text = " ".join([
        jd_text.lower(),
        " ".join(jd.get("all_skills", [])).lower(),
        " ".join(jd.get("domain_signals", [])).lower(),
    ])
    role_rules = [
        ("ai-data", ["data scientist", "data science", "machine learning", "llm", "rag", "nlp", "generative ai", "model evaluation"]),
        ("ios", ["ios", "swift", "uikit", "swiftui", "xcode", "mobile engineer"]),
        ("cloud-sre", ["sre", "cloud", "kubernetes", "gke", "aws", "azure", "devops", "infrastructure", "automation"]),
        ("backend-java", ["java", "spring boot", "backend", "microservices"]),
        ("full-stack", ["full-stack", "full stack", "react", "node.js", "frontend"]),
        ("systems-cpp-linux", ["c++", "linux", "unix", "operating systems", "networking"]),
    ]
    for role_type, signals in role_rules:
        if any(signal in text for signal in signals):
            return role_type
    return "general-software"


def export_resume_documents(out_dir: Path) -> list[Path]:
    markdown_path = out_dir / "tailored_resume.md"
    if not markdown_path.exists():
        return []
    docx_path = out_dir / "tailored_resume.docx"
    pdf_path = out_dir / "tailored_resume.pdf"
    tex_path = out_dir / "tailored_resume.tex"

    try:
        from export_resume import build_docx, build_latex, compile_latex, applicant_resume_lines
    except Exception:
        if not BUNDLED_PYTHON.exists():
            return []
        try:
            subprocess.run(
                [str(BUNDLED_PYTHON), str(Path(__file__).with_name("export_resume.py")), str(markdown_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return [path for path in [docx_path, tex_path, pdf_path] if path.exists()]

    lines = applicant_resume_lines(markdown_path.read_text(encoding="utf-8"))
    if pdf_path.exists():
        pdf_path.unlink()

    # LaTeX is the canonical source artifact and must not depend on DOCX/PDF success.
    try:
        build_latex(lines, tex_path)
    except Exception:
        pass
    try:
        build_docx(lines, docx_path)
    except Exception:
        pass
    try:
        if tex_path.exists():
            compile_latex(tex_path, pdf_path)
    except Exception:
        pass
    return [path for path in [docx_path, tex_path, pdf_path] if path.exists()]


def archive_role_package(out_dir: Path, role_type: str, slug: str) -> Path:
    role_dir = Path("document_resumes") / role_type / slug
    role_dir.mkdir(parents=True, exist_ok=True)
    keep = [
        "tailored_resume.md",
        "tailored_resume.tex",
        "tailored_resume.docx",
        "tailored_resume.pdf",
        "cover_letter.md",
        "cover_letter.txt",
        "cover_letter.tex",
        "cover_letter.docx",
        "cover_letter.pdf",
        "recruiter_dm.md",
        "application_brief.md",
        "skill_gap_project_plan.md",
        "interview_prep.md",
        "jd_analysis.json",
        "jd_source.txt",
        "source_metadata.json",
    ]
    for name in keep:
        source = out_dir / name
        if source.exists():
            shutil.copy2(source, role_dir / name)
        else:
            stale = role_dir / name
            if stale.exists():
                stale.unlink()
    return role_dir


def generate_application_package(
    *,
    vault_path: Path,
    out_root: Path,
    jd_text: str,
    source: str,
    slug: str,
    limit: int = 12,
    additional_instructions: str = "",
    attached_resume_text: str = "",
    attached_resume_name: str = "",
    company_name: str = "",
    role_name: str = "",
    cover_letter_instructions: str = "",
) -> dict[str, Any]:
    vault = json.loads(vault_path.read_text(encoding="utf-8"))
    jd = extract_jd(jd_text, flatten_skills(vault))
    role_type = infer_role_type(jd, jd_text)
    base_source = ROLE_TYPE_BASE_SOURCE.get(role_type)
    bullets = select_bullets(vault, jd, limit, base_source=base_source)

    out_dir = out_root / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = vault.get("profile", {})

    (out_dir / "jd_source.txt").write_text(jd_text, encoding="utf-8")
    (out_dir / "additional_instructions.txt").write_text(
        additional_instructions.strip() + ("\n" if additional_instructions.strip() else ""),
        encoding="utf-8",
    )
    (out_dir / "source_metadata.json").write_text(
        json.dumps({
            "source": source,
            "role_type": role_type,
            "base_resume_source": base_source,
            "attached_resume": attached_resume_name,
            "additional_instructions": additional_instructions.strip(),
            "cover_letter_instructions": cover_letter_instructions.strip(),
            "company_name": company_name.strip(),
            "role_name": role_name.strip(),
        }, indent=2),
        encoding="utf-8",
    )
    (out_dir / "jd_analysis.json").write_text(json.dumps(jd, indent=2), encoding="utf-8")
    (out_dir / "application_brief.md").write_text(render_application_brief(jd, bullets, source), encoding="utf-8")
    (out_dir / "skill_gap_project_plan.md").write_text(render_skill_gap_project_plan(jd, vault), encoding="utf-8")
    (out_dir / "tailored_resume.md").write_text(render_resume(vault, bullets, jd, role_type), encoding="utf-8")
    cover_letter = render_cover(
        profile,
        jd,
        bullets,
        cover_letter_instructions,
        attached_resume_text,
        company_name,
        role_name,
    )
    (out_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
    (out_dir / "cover_letter.txt").write_text(cover_letter, encoding="utf-8")
    (out_dir / "cover_letter.tex").write_text(
        render_cover_latex(cover_letter, profile),
        encoding="utf-8",
    )
    try:
        from export_cover_letter_pdf import build_cover_letter_pdf
        build_cover_letter_pdf(
            cover_letter,
            {
                "name": str(profile.get("name", "")),
                "email": str(profile.get("email", "")),
                "phone": str(profile.get("phone", "")),
            },
            out_dir / "cover_letter.pdf",
        )
    except Exception:
        if BUNDLED_PYTHON.exists():
            try:
                subprocess.run(
                    [
                        str(BUNDLED_PYTHON),
                        str(Path(__file__).with_name("export_cover_letter_pdf.py")),
                        str(out_dir / "cover_letter.txt"),
                        str(out_dir / "cover_letter.pdf"),
                        str(profile.get("name", "")),
                        str(profile.get("email", "")),
                        str(profile.get("phone", "")),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError):
                pass
    try:
        from export_resume import build_cover_letter_docx
        build_cover_letter_docx(
            cover_letter,
            {
                "name": str(profile.get("name", "")),
                "email": str(profile.get("email", "")),
                "phone": str(profile.get("phone", "")),
            },
            out_dir / "cover_letter.docx",
        )
    except Exception:
        if BUNDLED_PYTHON.exists():
            try:
                subprocess.run(
                    [
                        str(BUNDLED_PYTHON),
                        str(Path(__file__).with_name("export_cover_letter.py")),
                        str(out_dir / "cover_letter.md"),
                        str(out_dir / "cover_letter.docx"),
                        str(profile.get("name", "")),
                        str(profile.get("email", "")),
                        str(profile.get("phone", "")),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.SubprocessError):
                pass
    (out_dir / "recruiter_dm.md").write_text(render_dm(profile, jd, bullets), encoding="utf-8")
    (out_dir / "interview_prep.md").write_text(render_interview_notes(jd, bullets), encoding="utf-8")
    exported = export_resume_documents(out_dir)
    role_dir = archive_role_package(out_dir, role_type, slug)
    write_tracker_row(out_root, source, jd, bullets)

    return {
        "out_dir": out_dir,
        "role_dir": role_dir,
        "role_type": role_type,
        "base_source": base_source,
        "bullets": bullets,
        "jd": jd,
        "exported": exported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jd", type=Path, nargs="?", help="Path to a plain-text job description")
    parser.add_argument("--url", help="Job posting URL to fetch and tailor against")
    parser.add_argument("--vault", type=Path, default=Path("vault/career_vault.json"))
    parser.add_argument("--out", type=Path, default=Path("generated"))
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    if args.jd and args.url:
        raise SystemExit("Use either a JD file path or --url, not both.")

    jd_text, source, slug = read_jd_source(args)
    result = generate_application_package(
        vault_path=args.vault,
        out_root=args.out,
        jd_text=jd_text,
        source=source,
        slug=slug,
        limit=args.limit,
    )

    print(f"Wrote application package to {result['out_dir']}")
    print(f"Archived role package to {result['role_dir']}")
    if result["exported"]:
        print("Exported resume documents: " + ", ".join(str(path.name) for path in result["exported"]))
    print(f"Selected {len(result['bullets'])} truthful bullets from the vault")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
