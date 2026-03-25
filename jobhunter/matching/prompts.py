"""LLM prompt templates for CV-to-job matching."""

from __future__ import annotations

from jobhunter.models import JobPost

# ---------------------------------------------------------------------------
# Single-job prompts (unchanged)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert career advisor and talent matching specialist. Your job is to objectively \
evaluate how well a candidate's CV aligns with a specific job posting.

You will be given a candidate's CV and a job posting. Evaluate the match across EXACTLY these \
seven categories:

1. tech_stack    — Technical skills, tools, frameworks, and programming languages alignment.
2. experience    — Years of experience, seniority level, and type of work experience match.
3. location      — Geographic or remote-work compatibility between candidate and role.
4. education     — Educational background, degrees, certifications, and formal training relevance.
5. soft_skills   — Communication, leadership, teamwork, problem-solving indicators.
6. work_type     — Remote / hybrid / on-site preference alignment.
7. salary        — Salary expectation vs. listed compensation (score 0.5 if no data available).

For each category provide:
- score: float between 0.0 and 1.0 (0 = no match, 1 = perfect match)
- matches: list of 1–5 specific, concrete points where the CV aligns with the job
- mismatches: list of 1–5 specific gaps or concerns
- notes: one sentence summarising the category assessment

Also provide:
- top_matches: list of 3 strongest overall alignment points (across all categories)
- top_gaps: list of 3 most significant gaps the candidate should address
- recommendation: 2–3 sentences of career advice for this specific application
- apply_recommended: true if the candidate should apply, false if not

IMPORTANT: Respond with ONLY valid JSON. No markdown fences, no commentary outside the JSON.\
"""


def build_user_prompt(cv_text: str, job: JobPost) -> str:
    """Build the user-turn prompt for a CV ↔ job match evaluation."""
    salary_display = job.salary_display if job.has_salary else "Not listed"

    exp_display = "Not specified"
    if job.experience_years_min is not None or job.experience_years_max is not None:
        lo = job.experience_years_min
        hi = job.experience_years_max
        if lo and hi:
            exp_display = f"{lo}–{hi} years"
        elif lo:
            exp_display = f"{lo}+ years"
        elif hi:
            exp_display = f"Up to {hi} years"

    lines = [
        "## Candidate CV",
        "",
        cv_text.strip(),
        "",
        "## Job Posting",
        "",
        f"Title:               {job.title}",
        f"Company:             {job.company}",
        f"Location:            {job.location}",
        f"Work Type:           {job.work_type.value if job.work_type else 'Not specified'}",
        f"Experience Required: {exp_display}",
        f"Salary:              {salary_display}",
        f"Source:              {job.source.value}",
        "",
        "### Description",
        "",
        job.description.strip(),
    ]

    if job.requirements:
        lines += ["", "### Requirements", ""]
        lines += [f"- {r}" for r in job.requirements]

    if job.tech_stack:
        lines += ["", "### Tech Stack", ""]
        lines += [f"- {t}" for t in job.tech_stack]

    lines += [
        "",
        "## Your Task",
        "",
        "Return a JSON object with this exact structure:",
        "",
        '{',
        '  "categories": {',
        '    "tech_stack":  {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "experience":  {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "location":    {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "education":   {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "soft_skills": {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "work_type":   {"score": 0.0, "matches": [], "mismatches": [], "notes": ""},',
        '    "salary":      {"score": 0.0, "matches": [], "mismatches": [], "notes": ""}',
        '  },',
        '  "top_matches": ["...", "...", "..."],',
        '  "top_gaps": ["...", "...", "..."],',
        '  "recommendation": "...",',
        '  "apply_recommended": true',
        '}',
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch prompts — send N jobs in one call, get back a JSON array
# ---------------------------------------------------------------------------

BATCH_SYSTEM_PROMPT = """\
You are an expert career advisor and talent matching specialist. You will evaluate a \
candidate's CV against MULTIPLE job postings and return a scored assessment for each one.

For EACH job, evaluate the match across EXACTLY these seven categories:

1. tech_stack    — Technical skills, tools, frameworks, and programming languages alignment.
2. experience    — Years of experience, seniority level, and type of work experience match.
3. location      — Geographic or remote-work compatibility between candidate and role.
4. education     — Educational background, degrees, certifications, and formal training relevance.
5. soft_skills   — Communication, leadership, teamwork, problem-solving indicators.
6. work_type     — Remote / hybrid / on-site preference alignment.
7. salary        — Salary expectation vs. listed compensation (score 0.5 if no data available).

For each category provide:
- score: float between 0.0 and 1.0 (0 = no match, 1 = perfect match)

Also provide per job:
- top_matches: list of 3 strongest overall alignment points (across all categories)
- top_gaps: list of 3 most significant gaps the candidate should address
- apply_recommended: true if the candidate should apply, false if not

IMPORTANT: Respond with ONLY a valid JSON array. Each element must correspond to one job \
in the exact order provided. No markdown fences, no commentary outside the JSON.\
"""

# Max chars to include per job description in a batch prompt (keeps token count predictable)
_BATCH_DESC_LIMIT = 800
_BATCH_REQ_LIMIT = 5
_BATCH_TECH_LIMIT = 10


def build_batch_user_prompt(cv_text: str, jobs: list[JobPost]) -> str:
    """Build a single prompt that asks the LLM to score all *jobs* against the CV at once.

    Returns a prompt whose expected response is a JSON array with ``len(jobs)`` elements,
    one per job in the same order.
    """
    lines = [
        "## Candidate CV",
        "",
        cv_text.strip(),
        "",
        f"## Jobs to Evaluate ({len(jobs)} jobs)",
    ]

    for idx, job in enumerate(jobs, start=1):
        salary_display = job.salary_display if job.has_salary else "Not listed"

        exp_display = "Not specified"
        lo = job.experience_years_min
        hi = job.experience_years_max
        if lo and hi:
            exp_display = f"{lo}–{hi} years"
        elif lo:
            exp_display = f"{lo}+ years"
        elif hi:
            exp_display = f"Up to {hi} years"

        lines += [
            "",
            f"### Job {idx}: {job.title} at {job.company}",
            "",
            f"Title:               {job.title}",
            f"Company:             {job.company}",
            f"Location:            {job.location}",
            f"Work Type:           {job.work_type.value if job.work_type else 'Not specified'}",
            f"Experience Required: {exp_display}",
            f"Salary:              {salary_display}",
            f"Source:              {job.source.value}",
            "",
            "#### Description",
            "",
            job.description.strip()[:_BATCH_DESC_LIMIT],
        ]

        if job.requirements:
            lines += ["", "#### Requirements", ""]
            lines += [f"- {r}" for r in job.requirements[:_BATCH_REQ_LIMIT]]

        if job.tech_stack:
            lines += ["", "#### Tech Stack", ""]
            lines += [f"- {t}" for t in job.tech_stack[:_BATCH_TECH_LIMIT]]

    lines += [
        "",
        "## Your Task",
        "",
        f"Return a JSON array with exactly {len(jobs)} objects (one per job, in the same order shown above):",
        "",
        "[",
        "  {",
        '    "categories": {',
        '      "tech_stack":  {"score": 0.0},',
        '      "experience":  {"score": 0.0},',
        '      "location":    {"score": 0.0},',
        '      "education":   {"score": 0.0},',
        '      "soft_skills": {"score": 0.0},',
        '      "work_type":   {"score": 0.0},',
        '      "salary":      {"score": 0.0}',
        "    },",
        '    "top_matches": ["...", "...", "..."],',
        '    "top_gaps": ["...", "...", "..."],',
        '    "apply_recommended": true',
        "  }",
        "]",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Recommendation-only prompt — single job, plain text output, no JSON
# ---------------------------------------------------------------------------

RECOMMENDATION_SYSTEM_PROMPT = """\
You are a career advisor. Given a candidate's CV and a specific job posting, write 2–3 sentences \
of personalised application advice: highlight the candidate's strongest selling points for this \
role, mention any gaps they should address, and conclude with a clear recommendation on whether \
to apply.

Respond with plain text only — no JSON, no markdown, no headings.\
"""


def build_recommendation_prompt(cv_text: str, job: JobPost) -> str:
    """Build a minimal prompt to generate a personalised recommendation for a single job."""
    salary_display = job.salary_display if job.has_salary else "Not listed"

    lines = [
        "## Candidate CV",
        "",
        cv_text.strip()[:3000],   # cap CV to keep the call cheap
        "",
        "## Job",
        "",
        f"Title:    {job.title}",
        f"Company:  {job.company}",
        f"Location: {job.location}",
        f"Salary:   {salary_display}",
        "",
        job.description.strip()[:600],
    ]

    if job.requirements:
        lines += ["", "Requirements:"]
        lines += [f"- {r}" for r in job.requirements[:5]]

    lines += ["", "Write your 2–3 sentence recommendation now:"]
    return "\n".join(lines)
