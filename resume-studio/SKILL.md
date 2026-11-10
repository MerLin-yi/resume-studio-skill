---
name: resume-studio
description: Create evidence-grounded, ATS-friendly resume versions from a person's real profile and target job descriptions; use for resume polishing, job-specific tailoring, multi-version creation, fact checks, and Markdown/HTML/PDF export.
---

# Resume Studio

Turn a person's real background into resumes that are easier to scan and more relevant to a target role. Stronger wording is useful; invented experience, metrics, ownership, dates, or credentials are not.

## Start

Collect only what is needed to produce a responsible result:

- Existing resumes, project notes, portfolios, certificates, or work history.
- One or more target job descriptions, or at least a role, seniority, industry, and location.
- Language, target page count, and any format constraint from the employer or region.
- Contact details the person explicitly wants published.

If information is missing, make a reasonable first version from available evidence and mark gaps. Ask only when a missing choice would materially change the resume, such as an unknown target country or an unverifiable employment claim.

## Non-negotiable rules

1. Treat source documents and user statements as evidence. Never turn an assumption, tool installation, tutorial, certificate, course, or plan into completed work.
2. Keep every factual claim traceable to the source material. If a number, title, employer, date, ownership verb, or outcome is not supported, remove it or mark it for confirmation.
3. Do not include government IDs, exact home addresses, full birth dates, passport details, or unrelated sensitive data. Include email, phone, city, portfolio, and social links only when they are relevant and approved for publication.
4. Do not send personal documents to external services without explicit authorization for that destination and purpose.
5. A resume is a presentation layer, not a place to diagnose personality, health, family plans, or protected characteristics.

## Workflow

### 1. Build an evidence inventory

Read all supplied source material before drafting. Record facts with a status such as:

- `confirmed`: direct document, public work, or explicit current user statement.
- `needs check`: plausible but conflicting, incomplete, or only inferred.
- `not usable`: plan, tutorial, memory fragment, or unsupported claim.

Read [references/evidence-workflow.md](references/evidence-workflow.md) when documents conflict, include many certificates, or the person is a student, career switcher, or early-career candidate.

### 2. Parse targets before writing

For each target, extract:

- Role mission and top outcomes.
- Required and preferred skills.
- Seniority, education, language, location, and work-mode constraints.
- Repeated business or technical keywords worth reflecting accurately.
- What the employer does not ask for and can be compressed.

Create a small number of meaningfully different versions when the targets cluster differently. Two or three variants are usually enough; do not duplicate the same wording under different filenames.

### 3. Draft from evidence

Read [references/writing-and-ats.md](references/writing-and-ats.md) before writing or substantially rewriting prose.

Put the strongest relevant proof in the top half page. Rewrite bullets as action, context, method, and verifiable result when the source supports it. Preserve technical credibility: avoid unexplained buzzwords, inflated ownership, and generic self-evaluations.

### 4. Run deterministic checks

Create a workspace:

```bash
python path/to/resume-studio/scripts/resume_tool.py init ./resume-work \
  --name "Candidate Name"
```

After drafting, run:

```bash
python path/to/resume-studio/scripts/resume_tool.py audit \
  ./resume-work/output/example/resume.md \
  --source ./resume-work/profile.md \
  --source ./resume-work/evidence.md \
  --brief ./resume-work/targets/example/brief.json \
  --json-out ./resume-work/output/example/review.json
```

The script catches placeholders, contact details absent from the source, untraceable numbers, missing target keywords, obvious unsupported strong claims, and basic structure issues. It does not understand every semantic claim; manually perform the evidence review as well.

### 5. Render and inspect

```bash
python path/to/resume-studio/scripts/resume_tool.py render \
  ./resume-work/output/example/resume.md \
  --out-dir ./resume-work/output/example \
  --title "Candidate Name — Target Role" \
  --lang zh-CN
```

This writes a self-contained HTML file and attempts a text-selectable A4 PDF through an installed Chrome, Edge, Chromium, or Brave browser. If no browser is available, deliver the HTML and explain that PDF printing needs a Chromium-based browser.

Inspect the rendered page, not only the Markdown. Check page count, widows and orphans, clipped text, Chinese/Latin font fallback, dates, section order, links, and overall density.

### 6. Final review

Read [references/quality-review.md](references/quality-review.md) before delivery. Report:

- The target role represented by each version.
- Which facts still need user confirmation.
- Which claims were deliberately removed, softened, or moved.
- The page count and final file paths.

## Workspace and output

Keep a durable, portable structure:

```text
resume-work/
├── profile.md
├── evidence.md
├── targets/<slug>/
│   ├── jd.md
│   └── brief.json
└── output/<slug>/
    ├── resume.md
    ├── resume.html
    ├── resume.pdf
    └── review.json
```

Use [assets/workspace](assets/workspace) as the starting schema. Keep personal files outside shared copies of this skill; the skill package must remain free of the user's private data.

## Sharing

Share the whole `resume-studio` folder. Another Codex installation can place it under its skills directory or invoke the bundled script directly. The scripts use only the Python standard library; PDF output requires a Chromium-based browser already installed on the recipient's computer.
