# Resume Automation Workflow

Local MVP for tailoring applications from a truthful career vault.

## Local Web App

Start the interface:

```bash
python3 src/app_server.py
```

Then open `http://127.0.0.1:8765`.

On macOS, you can also double-click `Start Resume Studio.command`. Keep its Terminal window open while using the app; close it or press `Control-C` when finished.

The app accepts a job URL or pasted JD, an optional PDF/DOCX/TXT resume, and additional instructions. One generation creates the tailored resume, cover letter, recruiter DM, application brief, interview prep, and skill-gap plan. URL extraction automatically falls back to pasted JD text when a career site blocks scraping.

The cover-letter area has separate company, role, and instruction fields. It generates downloadable PDF and plain-text letters plus `cover_letter.tex`, a standalone LaTeX letter that can be pasted into Overleaf.

## Free Hosting

The repo includes `render.yaml` for Render:

1. Put the project in a private GitHub repository.
2. In Render, choose **New > Blueprint** and connect that repository.
3. Select the free instance and deploy.

The app reads Render's `PORT` automatically. Free Render services sleep after inactivity and use an ephemeral filesystem, so generated files should be downloaded immediately. Because resumes contain personal data, keep the source repository private and add authentication before sharing the deployed URL broadly.

## What it does

For each job description, the CLI:

1. Extracts required/preferred skills, responsibilities, keywords, seniority, and domain signals.
2. Scores your career-vault bullets against the JD.
3. Pulls only existing, sourced bullets from the vault.
4. Generates:
   - tailored resume Markdown
   - tailored resume DOCX
   - tailored resume TEX, plus PDF when a LaTeX compiler is installed
   - short cover letter/message
   - recruiter DM
   - application tracker CSV row
   - interview prep notes
   - JD analysis JSON

## Quick Start

1. Paste a job URL into the command:

```bash
python3 src/resume_tailor.py --url "https://company.com/jobs/example-role" --vault vault/career_vault.json
```

2. Or save a job description as `jds/company-role.txt` and run:

```bash
python3 src/resume_tailor.py jds/company-role.txt --vault vault/career_vault.json
```

Generated files will appear under `generated/<job-slug>/`.

The most useful file for fast review is `application_brief.md`. It lists the exact source-backed points to use, why each matched the JD, and which resume version supports it.

The same applicant-facing package is copied into `document_resumes/<role-type>/<job-slug>/`, so finished resumes stay organized by role family. Current role folders include examples such as `ai-data`, `ios`, `cloud-sre`, `backend-java`, `full-stack`, and `systems-cpp-linux`.

## Resume Format Rules

- Generate the resume as real LaTeX (`tailored_resume.tex`) and compile that LaTeX to PDF when a compiler such as `pdflatex`, `xelatex`, or `tectonic` is installed.
- Keep the provided LaTeX template spacing and structure unchanged. Do not tune margins, section spacing, bullet spacing, font sizes, or heading macros to force fit; adjust content selection instead.
- Keep the resume at a minimum of one full page; do not leave large empty whitespace.
- Add relevant and slightly relevant truthful experience when needed to fill the page.
- Maximum length is about two pages, and only when the role genuinely needs that much relevant detail.
- Follow the LaTeX-style structure in `templates/resume_structure_reference.tex`.
- Keep Education readable; do not over-compress school/GPA and degree rows.
- Use compact section headings with divider rules.
- Keep education, publications, and awards stable from the career vault.
- Tailor only summary, work experience, projects, and role-relevant skills.
- Start from the closest uploaded role resume and keep its existing work experience and projects; tailor by lightly editing emphasis, reordering, and adding only a few JD-relevant sourced bullets.
- Do not cap away base-resume bullets inside an existing role or project. If content needs shortening, choose less-relevant added bullets first rather than removing the user's existing base resume content.
- Do not rebuild the resume from only the highest-scoring bullets because that drops too much of the user's real experience.
- Any added or suggested point must be specific to the user's actual work: include concrete tools, systems, datasets, metrics, architecture, or domain context. Avoid generic bullets such as "worked on AI solutions" or "improved processes."
- Optimize for ATS matching and recruiter scanning: role-aligned title, compact skills, strong first bullets, concrete proof, and no vague filler.
- Only for the `Virginia Tech - CodeKids` role, use `AI Engineer` as the displayed title for AI/ML roles and `Software Engineer` for SDE/full-stack/backend/cloud/systems roles. Keep other role titles unchanged.
- Keep Technical Skills as subheaded rows, such as `Languages`, `AI/ML`, and `Technologies/Frameworks`.
- If ATS asks for similar technologies, prefer exact truthful matches first, then adjacent technologies from the same family. Examples: AWS/GCP/Azure in cloud, or React/Angular/TypeScript/Node.js in frontend/full-stack.
- Do not invent direct experience with a missing skill. Generate `skill_gap_project_plan.md` with a one-week project plan so the skill can be added only after it is actually built.
- Avoid irrelevant details even if they have strong metrics.

## Guardrails

- The generator never creates new experience bullets.
- Every selected bullet must have a `source_id`.
- Skills are only shown when they appear in your vault.
- The default resume keeps bullet wording unchanged.
- The URL text is saved as `jd_source.txt` so each generated package is auditable.
- Use the output as a strong first draft, then manually review before submitting.

## Source Files

The current vault was built from your existing resume PDFs. `.docx` versions are optional but useful for cleaner link extraction, exact formatting references, and less noisy source text. They are not required to generate tailored applications.

## Suggested Vault Routine

Keep the vault current as a living record:

- Add project wins immediately after they happen.
- Include exact metrics, even rough ranges when true.
- Tag each bullet with skills, domains, and evidence links.
- Keep older resume versions in `vault/resume_versions/` if useful.
- Add notes about company/domain context when it helps prove relevance.
